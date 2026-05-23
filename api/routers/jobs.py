"""Job queue and history endpoints."""
import csv
import json
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel

BASE_DIR = Path(__file__).parent.parent.parent
JOBS_CSV  = BASE_DIR / "jobs.csv"
OUTPUT_DIR = BASE_DIR / "output"

router = APIRouter()


def _read_jobs_csv() -> list:
    if not JOBS_CSV.exists():
        return []
    try:
        import pandas as pd
        df = pd.read_csv(JOBS_CSV)
        return df.fillna("").to_dict("records")
    except Exception:
        return []


def _read_results(profile: Optional[str] = None) -> list:
    """Read results from JSONL (authoritative) — immune to CSV schema corruption."""
    import json as _json
    import math as _math

    def _sanitize(obj):
        """Replace NaN/inf floats with empty string (not JSON-serializable)."""
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize(v) for v in obj]
        if isinstance(obj, float) and (_math.isnan(obj) or _math.isinf(obj)):
            return ""
        return obj

    results = []
    pattern = f"results_{profile}.jsonl" if profile else "results_*.jsonl"
    for jsonl_path in OUTPUT_DIR.glob(pattern):
        try:
            with open(jsonl_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        results.append(_sanitize(_json.loads(line)))
                    except Exception:
                        pass
        except Exception:
            pass
    return results


class AddJobRequest(BaseModel):
    url: str
    company: str = ""
    title: str = ""
    priority: str = "MED"
    notes: str = ""


@router.get("/queue")
def get_queue():
    return _read_jobs_csv()


@router.get("/history")
def get_history(
    profile: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    fit_label: Optional[str] = Query(None),
):
    results = _read_results(profile)
    if status:
        results = [r for r in results if r.get("status", "") == status]
    if fit_label:
        results = [r for r in results if r.get("fit_label", "") == fit_label]
    return results


@router.post("/add")
def add_job(body: AddJobRequest):
    import pandas as pd
    try:
        if JOBS_CSV.exists():
            df    = pd.read_csv(JOBS_CSV)
            max_id = int(df["id"].max()) if not df.empty else 0
        else:
            df    = pd.DataFrame(columns=["id","url","company","title","priority","notes"])
            max_id = 0

        new_id = max_id + 1
        new_row = {
            "id": new_id, "url": body.url, "company": body.company,
            "title": body.title, "priority": body.priority, "notes": body.notes,
        }
        pd.DataFrame([new_row]).to_csv(
            JOBS_CSV, mode="a", header=not JOBS_CSV.exists(), index=False
        )
        return {"job": new_row}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{job_id}")
def delete_job(job_id: int):
    import pandas as pd
    try:
        if not JOBS_CSV.exists():
            raise HTTPException(status_code=404, detail="No jobs CSV")
        df = pd.read_csv(JOBS_CSV)
        df = df[df["id"] != job_id]
        df.to_csv(JOBS_CSV, index=False)
        return {"deleted": job_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import")
async def import_jobs(file: UploadFile = File(...)):
    import pandas as pd
    import io
    try:
        content = await file.read()
        new_df  = pd.read_csv(io.StringIO(content.decode()))
        if "url" not in new_df.columns:
            raise HTTPException(status_code=400, detail="CSV must have 'url' column")

        if JOBS_CSV.exists():
            df     = pd.read_csv(JOBS_CSV)
            max_id = int(df["id"].max()) if not df.empty else 0
            existing = set(df["url"].dropna().astype(str))
        else:
            df     = pd.DataFrame(columns=["id","url","company","title","priority","notes"])
            max_id = 0
            existing = set()

        added = 0
        rows  = []
        for _, row in new_df.iterrows():
            url = str(row.get("url","")).strip()
            if not url or url in existing:
                continue
            max_id += 1
            rows.append({
                "id": max_id, "url": url,
                "company":  row.get("company", ""),
                "title":    row.get("title", ""),
                "priority": row.get("priority", "MED"),
                "notes":    row.get("notes", ""),
            })
            existing.add(url)
            added += 1

        if rows:
            pd.DataFrame(rows).to_csv(JOBS_CSV, mode="a", header=not JOBS_CSV.exists(), index=False)
        return {"added": added}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/review_queue")
def get_review_queue(profile: Optional[str] = Query(None)):
    """Return applications flagged for human review."""
    path = OUTPUT_DIR / "needs_review.jsonl"
    if not path.exists():
        return []
    records = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    if profile and r.get("profile") != profile:
                        continue
                    records.append(r)
                except Exception:
                    pass
    except Exception:
        pass
    return records


@router.get("/stats")
def get_stats(profile: Optional[str] = Query(None)):
    results = _read_results(profile)
    total   = len(results)
    by_status: dict = {}
    by_fit: dict    = {}
    for r in results:
        s = r.get("status", "unknown")
        f = r.get("fit_label", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        by_fit[f]    = by_fit.get(f, 0) + 1
    return {"total": total, "by_status": by_status, "by_fit": by_fit}
