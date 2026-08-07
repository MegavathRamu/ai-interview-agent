"""AI Interview Agent -- single endpoint per the technical spec: POST /api/interview.

No authentication. State is kept server-side per sessionId. A request with a
"candidate" field (re)starts the interview for that sessionId; a request with
a "message" field continues it.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.interview import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("interview.api")

app = FastAPI(title="AI Interview Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class InterviewRequest(BaseModel):
    sessionId: str
    candidate: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class Feedback(BaseModel):
    summary: str
    strengths: List[str]
    gaps: List[str]
    next: List[str]


class InterviewResponse(BaseModel):
    reply: str
    done: bool
    feedback: Optional[Feedback] = None


@app.post("/api/interview", response_model=InterviewResponse)
def interview(req: InterviewRequest) -> Dict[str, Any]:
    session_id = (req.sessionId or "").strip()
    if not session_id:
        raise HTTPException(status_code=422, detail="'sessionId' is required and cannot be empty.")

    if req.candidate is not None:
        try:
            return engine.start_session(session_id, req.candidate)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception:
            logger.exception("Failed to start interview for session %s", session_id)
            raise HTTPException(status_code=500, detail="Failed to start the interview. Please try again.")

    if req.message is not None:
        try:
            result = engine.handle_turn(session_id, req.message)
        except Exception:
            logger.exception("Failed to process turn for session %s", session_id)
            raise HTTPException(status_code=500, detail="Failed to process your response. Please try again.")
        if result.get("error") == "not_found":
            raise HTTPException(status_code=404, detail=result["reply"])
        return result

    raise HTTPException(
        status_code=422,
        detail="Request must include either 'candidate' (to start an interview) or 'message' (to continue one).",
    )


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}
