"""
Matches router - Resume-Job matching results
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from sqlalchemy import text
import json

from app.db.session import get_db
from app.models.job import Match
from app.models.user import User
from pydantic import BaseModel
from app.services.scoring import compute_fit_score, build_suggested_resume_draft
from app.services.ml_fit import predict_fit_probability
from app.services.ingestion import extract_resume_text, fetch_job_text_from_url
from app.core.security import get_authenticated_user

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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Get match results for resumes vs jobs"""
    from sqlalchemy import select
    
    query = select(Match).where(Match.user_id == current_user.id)
    
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


@router.post("/compute-from-file-url")
async def compute_match_from_file_url(
    resume_file: UploadFile = File(...),
    job_url: str = Form(...),
    resume_id: str | None = Form(None),
    job_id: str | None = Form(None),
    use_ml_model: bool = Form(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """
    Compute match from uploaded resume file and job URL.
    """
    try:
        resume_bytes = await resume_file.read()
        resume_text = await extract_resume_text(
            filename=resume_file.filename or "",
            content=resume_bytes,
        )
        job_text = await fetch_job_text_from_url(job_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Input processing failed: {type(exc).__name__}")


    result = compute_fit_score(resume_text, job_text)
    ml_probability = None
    ml_info = {"loaded": False, "reason": "ml_disabled"}
    if use_ml_model:
        ml_probability, ml_info = predict_fit_probability(
            semantic_score=result.semantic_score,
            keyword_coverage=result.keyword_coverage,
            ats_risk_score=result.ats_risk_score,
        )
    suggested_resume_text = build_suggested_resume_draft(
        resume_text=resume_text,
        missing_keywords=result.top_missing_keywords,
    )

    suggestion_payload = {
        "recommendations": result.explanation.get("recommendations", []),
        "top_missing_keywords": result.top_missing_keywords,
        "top_matched_keywords": result.top_matched_keywords,
    }

    # Store request audit: job link, resume snapshot, suggested changes, and timestamp.
    await db.execute(
        text(
            """
            INSERT INTO match_requests (
              user_id,
              resume_id,
              job_id,
              job_url,
              resume_filename,
              resume_text_used,
              suggested_changes_json,
              suggested_resume_text,
              fit_index,
              semantic_score,
              keyword_coverage,
              ats_risk_score,
              ml_fit_probability
            ) VALUES (
              :user_id,
              CAST(NULLIF(:resume_id, '') AS UUID),
              CAST(NULLIF(:job_id, '') AS UUID),
              :job_url,
              :resume_filename,
              :resume_text_used,
              CAST(:suggested_changes_json AS JSONB),
              :suggested_resume_text,
              :fit_index,
              :semantic_score,
              :keyword_coverage,
              :ats_risk_score,
              :ml_fit_probability
            )
            """
        ),
        {
            "user_id": str(current_user.id),
            "resume_id": resume_id or "",
            "job_id": job_id or "",
            "job_url": job_url,
            "resume_filename": resume_file.filename,
            "resume_text_used": resume_text,
            "suggested_changes_json": json.dumps(suggestion_payload),
            "suggested_resume_text": suggested_resume_text,
            "fit_index": result.fit_index,
            "semantic_score": result.semantic_score,
            "keyword_coverage": result.keyword_coverage,
            "ats_risk_score": result.ats_risk_score,
            "ml_fit_probability": ml_probability,
        },
    )
    await db.commit()

    return {
        "message": "Match score computed from file + URL",
        "resume_id": resume_id,
        "job_id": job_id,
        "job_url": job_url,
        "fit_index": result.fit_index,
        "semantic_score": result.semantic_score,
        "keyword_coverage": result.keyword_coverage,
        "ats_risk_score": result.ats_risk_score,
        "ml_fit_probability": round(ml_probability, 4) if ml_probability is not None else None,
        "ml_model_info": ml_info,
        "top_missing_keywords": result.top_missing_keywords,
        "top_matched_keywords": result.top_matched_keywords,
        "resume_text": resume_text,
        "suggested_resume_text": suggested_resume_text,
        "explanation_json": result.explanation,
    }


@router.get("/by-id/{match_id}")
async def get_match(
    match_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Get detailed match result"""
    match = await db.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if str(match.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Forbidden")
    
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


@router.get("/history/list")
async def list_match_request_history(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """
    List stored scoring request history from match_requests.
    """
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    result = await db.execute(
        text(
            """
            SELECT
              id,
              job_url,
              resume_filename,
              resume_text_used,
              fit_index,
              semantic_score,
              keyword_coverage,
              ats_risk_score,
              ml_fit_probability,
              suggested_resume_text,
              suggested_changes_json,
              requested_at
            FROM match_requests
            WHERE user_id = :user_id
            ORDER BY requested_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"limit": limit, "offset": offset, "user_id": str(current_user.id)},
    )
    rows = [dict(row._mapping) for row in result]

    for row in rows:
        if isinstance(row.get("suggested_changes_json"), str):
            try:
                row["suggested_changes_json"] = json.loads(row["suggested_changes_json"])
            except Exception:
                pass

    return {
        "history": rows,
        "limit": limit,
        "offset": offset,
        "count": len(rows),
    }
