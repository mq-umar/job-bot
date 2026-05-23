"""Bot control endpoints: start, stop, pause, status, captcha solved, review answer."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from api.bot_runner import BOT_STATE, start_session

router = APIRouter()


class StartConfig(BaseModel):
    profile: str = ""
    mode: str = "auto"          # auto | review
    limit: int = 25
    discover: bool = True
    companies_only: bool = False
    tier_max: int = 3
    min_score: float = 0.0
    dry_run: bool = False
    start_id: int = 1
    job_id: Optional[int] = None


class ReviewAnswer(BaseModel):
    answer: str  # y | n | q


@router.post("/start")
def start_bot(config: StartConfig):
    if BOT_STATE.status == "running":
        raise HTTPException(status_code=409, detail="Bot already running")
    ok = start_session(config.model_dump())
    if not ok:
        raise HTTPException(status_code=409, detail="Could not start session")
    return {"status": "started"}


@router.post("/stop")
def stop_bot():
    BOT_STATE.stop()
    return {"status": "stopped"}


@router.post("/pause")
def pause_bot():
    if BOT_STATE.status == "running":
        BOT_STATE.pause()
        return {"status": "paused"}
    if BOT_STATE.status == "paused":
        BOT_STATE.resume()
        return {"status": "running"}
    return {"status": BOT_STATE.status}


@router.get("/status")
def bot_status():
    return BOT_STATE.to_dict()


@router.post("/captcha/solved")
def captcha_solved():
    BOT_STATE.captcha_solved()
    return {"ok": True}


@router.post("/review")
def submit_review(body: ReviewAnswer):
    BOT_STATE.review_answer(body.answer)
    return {"ok": True}
