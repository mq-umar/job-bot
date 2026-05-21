"""
bot_runner.py — wraps the existing bot in a background thread.

Key design:
- One BotState singleton tracks current session
- LOG_QUEUE receives all log events (print output + structured events)
- builtins.input is patched while bot runs so interactive prompts go through events
- Bot aborts cleanly via threading.Event
"""
import builtins
import io
import json
import queue
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

LOG_QUEUE: queue.Queue = queue.Queue(maxsize=2000)
_original_input = builtins.input


# ── Log emission ──────────────────────────────────────────────────────────────

def emit(level: str, message: str,
         event_type: str = "log", data: Optional[Dict] = None) -> None:
    entry = {
        "type":      event_type,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "level":     level,
        "message":   message,
        "data":      data or {},
    }
    try:
        LOG_QUEUE.put_nowait(entry)
    except queue.Full:
        try:
            LOG_QUEUE.get_nowait()
        except queue.Empty:
            pass
        try:
            LOG_QUEUE.put_nowait(entry)
        except queue.Full:
            pass


# ── Stdout capture ────────────────────────────────────────────────────────────

class _LogCapture(io.TextIOBase):
    def write(self, text: str) -> int:
        stripped = text.strip()
        if stripped:
            emit("info", stripped)
        return len(text)

    def flush(self) -> None:
        pass


# ── Bot state ─────────────────────────────────────────────────────────────────

class BotState:
    def __init__(self):
        self.status: str = "idle"
        self.current_job: Optional[Dict] = None
        self.jobs_applied: int = 0
        self.jobs_total: int = 0
        self.session_config: Optional[Dict] = None
        self.session_submitted: int = 0
        self.session_failed: int = 0
        self.session_errors: int = 0
        self._abort   = threading.Event()
        self._pause   = threading.Event()
        self._captcha = threading.Event()
        self._review_ans: Optional[str] = None
        self._review  = threading.Event()
        self._lock    = threading.Lock()

    def reset(self) -> None:
        self._abort.clear()
        self._pause.clear()
        self._captcha.clear()
        self._review.clear()
        self._review_ans = None
        self.jobs_applied = 0
        self.jobs_total   = 0
        self.current_job  = None
        self.session_submitted = 0
        self.session_failed = 0
        self.session_errors = 0

    def stop(self) -> None:
        self._abort.set()
        self._captcha.set()  # unblock any waiting
        self._review.set()
        self.status = "stopped"

    def pause(self) -> None:
        if self.status == "running":
            self._pause.set()
            self.status = "paused"

    def resume(self) -> None:
        if self.status == "paused":
            self._pause.clear()
            self.status = "running"

    def captcha_solved(self) -> None:
        self._captcha.set()

    def review_answer(self, answer: str) -> None:
        self._review_ans = answer
        self._review.set()

    def to_dict(self) -> Dict:
        return {
            "status":            self.status,
            "current_job":       self.current_job,
            "jobs_applied":      self.jobs_applied,
            "jobs_total":        self.jobs_total,
            "session_submitted": self.session_submitted,
            "session_failed":    self.session_failed,
            "session_errors":    self.session_errors,
        }


BOT_STATE = BotState()


# ── Input patcher ─────────────────────────────────────────────────────────────

def _patched_input(prompt: str = "") -> str:
    """Replaces builtins.input while bot runs."""
    p = str(prompt).lower()

    if "start?" in p or "continue?" in p:
        # Auto-confirm start
        return "y"

    if "captcha" in p or "recaptcha" in p:
        emit("warning", str(prompt), event_type="captcha")
        BOT_STATE._captcha.wait(timeout=300)
        BOT_STATE._captcha.clear()
        return ""

    if "submit?" in p or "apply?" in p:
        if BOT_STATE.session_config and BOT_STATE.session_config.get("mode") == "review":
            emit("info", str(prompt), event_type="review")
            BOT_STATE._review.wait(timeout=120)
            BOT_STATE._review.clear()
            ans = BOT_STATE._review_ans or "y"
            BOT_STATE._review_ans = None
            return ans
        return "y"  # auto mode

    if "press enter" in p:
        return ""

    return "y"  # safe default


# ── Session runner ────────────────────────────────────────────────────────────

def run_session(config: Dict) -> None:
    """
    Run a complete bot session in the current thread.
    config keys: profile, mode, limit, discover, companies_only, tier_max,
                 min_score, dry_run, start_id, job_id
    """
    BOT_STATE.reset()
    BOT_STATE.status = "running"
    BOT_STATE.session_config = config

    profile_name = config.get("profile", "muhammad")
    dry_run      = config.get("dry_run", False)
    review       = config.get("mode", "auto") == "review"
    limit        = config.get("limit", 50)
    discover     = config.get("discover", False)
    companies_only = config.get("companies_only", False)
    tier_max     = config.get("tier_max", 4)
    min_score    = config.get("min_score", 0.0)
    start_id     = config.get("start_id", 1)
    job_id       = config.get("job_id", None)

    emit("info", f"Session starting — profile: {profile_name}, limit: {limit}",
         event_type="session_start")

    # Patch input + stdout
    builtins.input = _patched_input
    old_stdout = sys.stdout
    sys.stdout  = _LogCapture()

    # Will be set after imports so the finally block can restore them
    _main_module_ref: Any = None
    _orig_log_result: Any = None

    try:
        import random
        import time
        import pandas as pd
        from playwright.sync_api import sync_playwright

        from main import (
            load_profile, load_applied_urls, load_blacklist, normalize_url,
            log_result, _make_entry, process_job, SessionStats,
            OUTPUT_DIR, BROWSER_PROF,
        )
        from job_finder import discover_jobs, append_to_jobs_csv

        # Patch log_result to track live session stats and emit rich job_result events
        import main as _main_module_ref
        _orig_log_result = _main_module_ref.log_result

        def _tracking_log_result(profile_name_: str, entry: Dict) -> None:
            _orig_log_result(profile_name_, entry)
            status  = entry.get("status", "")
            company = entry.get("company", "")
            title   = entry.get("title", "")
            fit     = entry.get("fit_label", "")
            score   = entry.get("resume_score", "0")
            if status in ("submitted", "submitted_manually"):
                BOT_STATE.session_submitted += 1
            elif status == "submit_failed":
                BOT_STATE.session_failed += 1
            elif status == "error":
                BOT_STATE.session_errors += 1
            icon = ("✓" if status in ("submitted", "submitted_manually")
                    else "✗" if status in ("error", "submit_failed")
                    else "○")
            emit("info", f"{icon} {company} — {title} [{status}]",
                 event_type="job_result",
                 data={"company": company, "title": title, "status": status,
                       "fit_label": fit, "score": score})

        _main_module_ref.log_result = _tracking_log_result

        profile  = load_profile(profile_name)
        jobs_csv = BASE_DIR / "jobs.csv"
        if not jobs_csv.exists():
            emit("error", "jobs.csv not found")
            return

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        df = pd.read_csv(jobs_csv)
        df = df[df["url"].notna() & (df["url"].str.strip() != "")]
        if job_id:
            df = df[df["id"] == job_id]
        else:
            df = df[df["id"] >= start_id]

        applied_urls = load_applied_urls(profile_name)
        blacklist    = load_blacklist()
        stats        = SessionStats()
        jobs_run     = 0

        BOT_STATE.jobs_total = min(
            len(df[~df["url"].apply(lambda u: normalize_url(str(u)) in applied_urls)]),
            limit,
        )

        # ── Warn early if nothing to process ──────────────────────────────────
        if BOT_STATE.jobs_total == 0 and not discover:
            emit("warning",
                 f"No new jobs for '{profile_name}' — "
                 f"{stats.duplicates + len(applied_urls)} already applied. "
                 "Add more jobs to jobs.csv or enable Discovery mode.",
                 event_type="log")

        browser_dir = BROWSER_PROF / profile_name
        browser_dir.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            # Remove ALL stale Chrome lock files — top-level singleton locks AND
            # every LevelDB LOCK file inside the profile (left by unclean shutdowns)
            for lf in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
                (browser_dir / lf).unlink(missing_ok=True)
            for lock in browser_dir.rglob("LOCK"):
                try:
                    lock.unlink()
                except Exception:
                    pass

            # Reset Chrome crash state — prevents "Something went wrong with your
            # profile" dialog after an unclean shutdown (exit_type="Crashed")
            import json as _j
            _prefs_path = browser_dir / "Default" / "Preferences"
            if _prefs_path.exists():
                try:
                    with open(_prefs_path) as _f:
                        _prefs = _j.load(_f)
                    _p = _prefs.get("profile", {})
                    if _p.get("exit_type") == "Crashed":
                        _p["exit_type"]      = "Normal"
                        _p["exited_cleanly"] = True
                        _prefs["profile"]    = _p
                        with open(_prefs_path, "w") as _f:
                            _j.dump(_prefs, _f, separators=(",", ":"))
                        emit("info", f"Fixed Chrome exit state for {profile_name}")
                except Exception:
                    pass

            _browser_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-first-run",
                "--no-default-browser-check",
            ]
            try:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(browser_dir),
                    headless=False,
                    channel="chrome",
                    args=_browser_args,
                    ignore_default_args=["--enable-automation"],
                    viewport={"width": 1440, "height": 900},
                )
            except Exception:
                # Fallback: use bundled Chromium if Chrome not installed
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(browser_dir),
                    headless=False,
                    args=_browser_args,
                    ignore_default_args=["--enable-automation"],
                    viewport={"width": 1440, "height": 900},
                )
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = context.new_page()

            try:
                # ── Phase 1: CSV jobs ─────────────────────────────────────
                for _, row in df.iterrows():
                    if BOT_STATE._abort.is_set():
                        break
                    if jobs_run >= limit:
                        break

                    # Pause support
                    while BOT_STATE._pause.is_set():
                        time.sleep(0.5)
                        if BOT_STATE._abort.is_set():
                            break

                    norm = normalize_url(str(row.get("url", "")))
                    if norm in applied_urls:
                        stats.duplicates += 1
                        continue

                    stats.discovered += 1
                    company = str(row.get("company", ""))
                    title   = str(row.get("title", ""))
                    BOT_STATE.current_job = {"company": company, "title": title}

                    emit("info", f"Applying to {title} at {company}",
                         event_type="job_start",
                         data={"company": company, "title": title,
                               "url": str(row.get("url", ""))})

                    result = process_job(
                        page, context, row.to_dict(), int(row.get("id", 0)),
                        profile, profile_name, applied_urls, stats,
                        dry_run=dry_run, review=review, min_score=min_score,
                        blacklist=blacklist,
                    )
                    jobs_run += 1
                    BOT_STATE.jobs_applied = jobs_run
                    emit("info", f"Done: {company} — {title}",
                         event_type="job_done",
                         data={"company": company, "title": title, "result": result})

                    if result == "stop" or BOT_STATE._abort.is_set():
                        break
                    time.sleep(random.uniform(2, 4))

                # ── Phase 2: Discovery ────────────────────────────────────
                if discover and not BOT_STATE._abort.is_set() and jobs_run < limit:
                    emit("info", "Starting job discovery...", event_type="log")
                    while jobs_run < limit and not BOT_STATE._abort.is_set():
                        new_jobs = discover_jobs(
                            page, context, profile_name, applied_urls,
                            max_per_search=20,
                            tier_max=tier_max,
                            companies_only=companies_only,
                        )
                        if not new_jobs:
                            break
                        added = append_to_jobs_csv(new_jobs)
                        if not added:
                            break
                        stats.discovered += len(added)
                        for job_row in added:
                            if jobs_run >= limit or BOT_STATE._abort.is_set():
                                break
                            while BOT_STATE._pause.is_set():
                                time.sleep(0.5)
                                if BOT_STATE._abort.is_set():
                                    break

                            company = str(job_row.get("company", ""))
                            title   = str(job_row.get("title", ""))
                            BOT_STATE.current_job = {"company": company, "title": title}
                            emit("info", f"[discover] {title} at {company}",
                                 event_type="job_start",
                                 data={"company": company, "title": title})

                            result = process_job(
                                page, context, job_row, job_row["id"],
                                profile, profile_name, applied_urls, stats,
                                dry_run=dry_run, review=review, min_score=min_score,
                                blacklist=blacklist,
                            )
                            jobs_run += 1
                            BOT_STATE.jobs_applied = jobs_run
                            if result == "stop":
                                BOT_STATE.stop()
                                break
                            time.sleep(random.uniform(2, 4))

            except Exception as e:
                emit("error", f"Session error: {e}", event_type="log")
            else:
                # ── Jobs done — emit summary then hold browser open ────────
                summary = {
                    "jobs_applied": jobs_run,
                    "submitted":    stats.submitted,
                    "failed":       stats.submit_failed,
                    "errors":       stats.errors,
                    "dry_run":      stats.dry_run,
                }
                if jobs_run == 0:
                    emit("warning",
                         f"No jobs processed for '{profile_name}'. "
                         f"All {len(applied_urls)} jobs in jobs.csv were already applied. "
                         "Add new URLs to jobs.csv or enable Discovery mode.",
                         event_type="log")
                emit("info",
                     f"Session complete — {stats.submitted} submitted, "
                     f"{stats.errors} errors",
                     event_type="summary", data=summary)
                emit("info",
                     "Browser staying open. Click Stop Bot to close it.",
                     event_type="log")
                # Hold browser open until user explicitly stops the session
                while not BOT_STATE._abort.is_set():
                    time.sleep(0.5)
            finally:
                try:
                    context.close()
                except Exception:
                    pass

    except Exception as e:
        emit("error", f"Fatal error: {e}", event_type="log")
    finally:
        if _main_module_ref is not None and _orig_log_result is not None:
            _main_module_ref.log_result = _orig_log_result
        builtins.input = _original_input
        sys.stdout     = old_stdout
        BOT_STATE.current_job = None
        if BOT_STATE.status == "running":
            BOT_STATE.status = "idle"


def start_session(config: Dict) -> bool:
    """Start a bot session in a background thread. Returns False if already running."""
    if BOT_STATE.status == "running":
        return False
    t = threading.Thread(target=run_session, args=(config,), daemon=True)
    t.start()
    return True
