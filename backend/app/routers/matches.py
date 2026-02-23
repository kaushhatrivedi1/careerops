"""
Matches router - Resume-Job matching results
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.db.session import get_db
from app.models.job import Match
from pydantic import BaseModel
from app.services.scoring import compute_fit_score
from app.services.ml_fit import predict_fit_probability

router = APIRouter()


class MatchResponse(BaseModel):
    id: str
    user_id: str
    resume_id: str
    job_id: str
    semantic_score: float
    keyword_coverage: float
    ats_risk_score: float
    overall_score: float
    explanation_json: dict
    created_at: datetime


class ComputeMatchRequest(BaseModel):
    resume_text: str
    job_text: str
    resume_id: str | None = None
    job_id: str | None = None
    use_ml_model: bool = True


@router.get("/")
async def get_matches(
    resume_id: str = None,
    job_id: str = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Get match results for resumes vs jobs"""
    from sqlalchemy import select
    
    user_id = "temp-user-id"  # TODO: Get from auth
    query = select(Match).where(Match.user_id == user_id)
    
    if resume_id:
        query = query.where(Match.resume_id == resume_id)
    if job_id:
        query = query.where(Match.job_id == job_id)
    
    query = query.offset(offset).limit(limit)
    
    result = await db.execute(query)
    matches = result.scalars().all()
    
    return {
        "matches": [
            {
                "id": str(m.id),
                "resume_id": str(m.resume_id),
                "job_id": str(m.job_id),
                "semantic_score": float(m.semantic_score) if m.semantic_score else None,
                "keyword_coverage": float(m.keyword_coverage) if m.keyword_coverage else None,
                "ats_risk_score": float(m.ats_risk_score) if m.ats_risk_score else None,
                "overall_score": float(m.overall_score) if m.overall_score else None,
                "explanation_json": m.explanation_json,
                "created_at": m.created_at
            }
            for m in matches
        ]
    }


@router.post("/compute")
async def compute_matches(
    payload: ComputeMatchRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Compute deterministic fit score and ATS guidance for a resume-job pair.
    """
    result = compute_fit_score(payload.resume_text, payload.job_text)
    ml_probability = None
    ml_info = {"loaded": False, "reason": "ml_disabled"}
    if payload.use_ml_model:
        ml_probability, ml_info = predict_fit_probability(
            semantic_score=result.semantic_score,
            keyword_coverage=result.keyword_coverage,
            ats_risk_score=result.ats_risk_score,
        )

    return {
        "message": "Match score computed",
        "resume_id": payload.resume_id,
        "job_id": payload.job_id,
        "fit_index": result.fit_index,
        "semantic_score": result.semantic_score,
        "keyword_coverage": result.keyword_coverage,
        "ats_risk_score": result.ats_risk_score,
        "ml_fit_probability": round(ml_probability, 4) if ml_probability is not None else None,
        "ml_model_info": ml_info,
        "top_missing_keywords": result.top_missing_keywords,
        "top_matched_keywords": result.top_matched_keywords,
        "explanation_json": result.explanation,
    }


@router.get("/{match_id}")
async def get_match(match_id: str, db: AsyncSession = Depends(get_db)):
    """Get detailed match result"""
    match = await db.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    return {
        "id": str(match.id),
        "resume_id": str(match.resume_id),
        "job_id": str(match.job_id),
        "semantic_score": float(match.semantic_score) if match.semantic_score else None,
        "keyword_coverage": float(match.keyword_coverage) if match.keyword_coverage else None,
        "ats_risk_score": float(match.ats_risk_score) if match.ats_risk_score else None,
        "overall_score": float(match.overall_score) if match.overall_score else None,
        "explanation_json": match.explanation_json,
        "created_at": match.created_at
    }
