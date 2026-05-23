"""Resume management endpoints: list, upload, delete, score."""
import shutil
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse

BASE_DIR     = Path(__file__).parent.parent.parent
_RESUMES_ROOT = (BASE_DIR / "resumes").resolve()

router = APIRouter()


def _safe_name(value: str, field: str = "name") -> str:
    """Reject path separators, traversal sequences, and null bytes."""
    if not value or ".." in value or "/" in value or "\\" in value or "\x00" in value:
        raise HTTPException(status_code=400, detail=f"Invalid {field}")
    return value


def _resume_dir(profile: str) -> Path:
    _safe_name(profile, "profile")
    path = BASE_DIR / "resumes" / profile
    # Double-check resolved path stays within resumes root
    try:
        path.resolve().relative_to(_RESUMES_ROOT)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid profile")
    return path


def _resume_stats(profile: str) -> dict:
    """Load usage stats from results CSVs."""
    stats: dict = {}
    output_dir = BASE_DIR / "output"
    for csv_path in output_dir.glob(f"results_{profile}.csv"):
        try:
            import pandas as pd
            df = pd.read_csv(csv_path)
            for _, row in df.iterrows():
                fname = row.get("selected_resume", "")
                if not fname:
                    continue
                if fname not in stats:
                    stats[fname] = {"times_used": 0, "scores": []}
                stats[fname]["times_used"] += 1
                try:
                    score = float(row.get("resume_score", 0))
                    if score > 0:
                        stats[fname]["scores"].append(score)
                except Exception:
                    pass
        except Exception:
            pass
    return stats


@router.get("/{profile}")
def list_resumes(profile: str):
    folder = _resume_dir(profile)
    if not folder.exists():
        return []
    stats = _resume_stats(profile)
    result = []
    for pdf in sorted(folder.glob("*.pdf")):
        stat = stats.get(pdf.name, {"times_used": 0, "scores": []})
        avg  = (sum(stat["scores"]) / len(stat["scores"])) if stat["scores"] else 0.0
        result.append({
            "filename":   pdf.name,
            "size_kb":    round(pdf.stat().st_size / 1024, 1),
            "times_used": stat["times_used"],
            "avg_score":  round(avg, 3),
        })
    return result


@router.post("/{profile}")
async def upload_resume(profile: str, file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files accepted")
    fname = Path(file.filename).name  # strip any directory components from filename
    _safe_name(fname, "filename")
    folder = _resume_dir(profile)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / fname
    try:
        with open(dest, "wb") as f:
            content = await file.read()
            f.write(content)
        return {"uploaded": fname, "size_kb": round(dest.stat().st_size / 1024, 1)}
    except Exception:
        raise HTTPException(status_code=500, detail="Upload failed")


@router.delete("/{profile}/{filename}")
def delete_resume(profile: str, filename: str):
    _safe_name(filename, "filename")
    path = _resume_dir(profile) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Resume not found")
    path.unlink()
    return {"deleted": filename}


@router.get("/{profile}/{filename}/score")
def score_resume(profile: str, filename: str, jd: str = Query(...)):
    _safe_name(filename, "filename")
    path = _resume_dir(profile) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Resume not found")
    try:
        import sys
        sys.path.insert(0, str(BASE_DIR))
        from resume_selector import score_resumes, fit_label, get_matched_keywords
        ranked   = score_resumes(jd, profile)
        score    = next((s for n, s in ranked if n == filename), 0.0)
        keywords = get_matched_keywords(jd, str(path))
        return {
            "filename":  filename,
            "score":     round(score, 3),
            "fit_label": fit_label(score),
            "keywords":  keywords,
            "ranking":   [{"filename": n, "score": round(s, 3)} for n, s in ranked[:5]],
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Scoring failed")


@router.get("/{profile}/{filename}/download")
def download_resume(profile: str, filename: str):
    _safe_name(filename, "filename")
    path = _resume_dir(profile) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Resume not found")
    return FileResponse(str(path), filename=filename, media_type="application/pdf")
