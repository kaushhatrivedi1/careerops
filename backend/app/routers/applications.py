"""
Applications router — track job applications and report outcomes for ML feedback.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_authenticated_user
from app.db.session import get_db
from app.models.job import Application
from app.models.resume import Resume
from app.models.user import User

router = APIRouter()

VALID_STATUSES = {"saved", "applied", "interview", "offer", "reject"}


class ApplicationCreate(BaseModel):
    resume_id: str
    # At least one of job_id or job_url must be provided
    job_id: Optional[str] = None
    job_url: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    status: str = "applied"
    cv_snapshot_text: Optional[str] = None
    fit_index: Optional[float] = None


class ApplicationResponse(BaseModel):
    id: str
    user_id: str
    job_id: Optional[str]
    resume_id: str
    job_url: Optional[str]
    company: Optional[str]
    role: Optional[str]
    status: str
    fit_index: Optional[float]
    applied_at: Optional[datetime]
    updated_at: datetime
    created_at: datetime


class OutcomePatch(BaseModel):
    status: str  # "interview" | "offer" | "reject"


@router.post("/", response_model=ApplicationResponse)
async def create_application(
    app_data: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Record a new job application."""
    if not app_data.job_id and not app_data.job_url:
        raise HTTPException(status_code=400, detail="Provide job_id or job_url")
    if app_data.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Use one of: {VALID_STATUSES}")

    resume = await db.get(Resume, app_data.resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    if str(resume.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Resume does not belong to user")

    app = Application(
        user_id=current_user.id,
        job_id=app_data.job_id or None,
        resume_id=app_data.resume_id,
        status=app_data.status,
        job_url=app_data.job_url,
        company=app_data.company,
        role=app_data.role,
        cv_snapshot_text=app_data.cv_snapshot_text,
        fit_index=str(app_data.fit_index) if app_data.fit_index is not None else None,
        applied_at=datetime.utcnow(),
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return _to_response(app)


@router.get("/")
async def list_applications(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List applications for the current user."""
    from sqlalchemy import select

    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    query = select(Application).where(Application.user_id == current_user.id)
    if status:
        query = query.where(Application.status == status)
    query = query.order_by(Application.applied_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    apps = result.scalars().all()
    return {"applications": [_to_response(a) for a in apps], "count": len(apps)}


@router.patch("/{app_id}/outcome")
async def report_outcome(
    app_id: str,
    payload: OutcomePatch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """
    Report interview/offer/reject outcome for an application.
    This is the primary feedback signal used to train the ML model.
    """
    if payload.status not in {"interview", "offer", "reject"}:
        raise HTTPException(status_code=400, detail="outcome must be: interview, offer, or reject")

    app = await db.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if str(app.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Forbidden")

    app.status = payload.status
    app.outcome_reported_at = datetime.utcnow()
    app.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(app)
    return _to_response(app)


@router.put("/{app_id}")
async def update_application(
    app_id: str,
    status: str,
    notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Update application status or notes."""
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Use one of: {VALID_STATUSES}")

    app = await db.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if str(app.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Forbidden")

    app.status = status
    if notes:
        app.notes = notes
    app.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(app)
    return _to_response(app)


@router.get("/stats")
async def application_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """
    Return per-user application statistics:
    - counts by status
    - interview rate and offer rate
    - top companies applied to
    - average fit_index by outcome
    """
    uid = str(current_user.id)

    counts_result = await db.execute(
        text(
            """
            SELECT status, COUNT(*) AS cnt
            FROM applications
            WHERE user_id = :uid
            GROUP BY status
            """
        ),
        {"uid": uid},
    )
    counts = {row.status: row.cnt for row in counts_result}

    total_applied = sum(counts.get(s, 0) for s in ("applied", "interview", "offer", "reject"))
    interview_rate = (
        round((counts.get("interview", 0) + counts.get("offer", 0)) / total_applied, 4)
        if total_applied else None
    )
    offer_rate = (
        round(counts.get("offer", 0) / total_applied, 4)
        if total_applied else None
    )

    top_companies_result = await db.execute(
        text(
            """
            SELECT company, COUNT(*) AS cnt
            FROM applications
            WHERE user_id = :uid AND company IS NOT NULL
            GROUP BY company
            ORDER BY cnt DESC
            LIMIT 10
            """
        ),
        {"uid": uid},
    )
    top_companies = [{"company": r.company, "count": r.cnt} for r in top_companies_result]

    avg_fit_result = await db.execute(
        text(
            """
            SELECT status, ROUND(AVG(fit_index::DOUBLE PRECISION)::NUMERIC, 2) AS avg_fit
            FROM applications
            WHERE user_id = :uid AND fit_index IS NOT NULL
            GROUP BY status
            """
        ),
        {"uid": uid},
    )
    avg_fit_by_outcome = {r.status: float(r.avg_fit) for r in avg_fit_result if r.avg_fit is not None}

    return {
        "total_tracked": sum(counts.values()),
        "by_status": counts,
        "interview_rate": interview_rate,
        "offer_rate": offer_rate,
        "top_companies": top_companies,
        "avg_fit_index_by_outcome": avg_fit_by_outcome,
    }


def _to_response(app: Application) -> ApplicationResponse:
    fit = None
    try:
        fit = float(app.fit_index) if app.fit_index is not None else None
    except (TypeError, ValueError):
        pass
    return ApplicationResponse(
        id=str(app.id),
        user_id=str(app.user_id),
        job_id=str(app.job_id) if app.job_id else None,
        resume_id=str(app.resume_id),
        job_url=app.job_url,
        company=app.company,
        role=app.role,
        status=app.status,
        fit_index=fit,
        applied_at=app.applied_at,
        updated_at=app.updated_at,
        created_at=app.created_at,
    )
