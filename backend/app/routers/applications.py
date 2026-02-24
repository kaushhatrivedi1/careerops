"""
Applications router
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.db.session import get_db
from app.models.job import Application
from app.models.resume import Resume
from app.models.user import User
from app.core.security import get_authenticated_user
from pydantic import BaseModel

router = APIRouter()


class ApplicationCreate(BaseModel):
    job_id: str
    resume_id: str
    status: str = "saved"


class ApplicationResponse(BaseModel):
    id: str
    user_id: str
    job_id: str
    resume_id: str
    status: str
    applied_at: datetime
    updated_at: datetime
    created_at: datetime


@router.post("/", response_model=ApplicationResponse)
async def create_application(
    app_data: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Create a new application"""
    # TODO: Validate job_id and resume_id exist and belong to user
    
    resume = await db.get(Resume, app_data.resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    if str(resume.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Resume does not belong to user")

    app = Application(
        user_id=current_user.id,
        job_id=app_data.job_id,
        resume_id=app_data.resume_id,
        status=app_data.status
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    
    return ApplicationResponse(
        id=str(app.id),
        user_id=str(app.user_id),
        job_id=str(app.job_id),
        resume_id=str(app.resume_id),
        status=app.status,
        applied_at=app.applied_at,
        updated_at=app.updated_at,
        created_at=app.created_at
    )


@router.get("/")
async def list_applications(
    status: str = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List applications for current user"""
    from sqlalchemy import select
    
    query = select(Application).where(Application.user_id == current_user.id)
    
    if status:
        query = query.where(Application.status == status)
    
    query = query.offset(offset).limit(limit)
    
    result = await db.execute(query)
    apps = result.scalars().all()
    
    return {
        "applications": [
            {
                "id": str(a.id),
                "job_id": str(a.job_id),
                "resume_id": str(a.resume_id),
                "status": a.status,
                "applied_at": a.applied_at,
                "updated_at": a.updated_at
            }
            for a in apps
        ]
    }


@router.put("/{app_id}")
async def update_application(
    app_id: str,
    status: str,
    notes: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Update application status"""
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
    
    return {
        "id": str(app.id),
        "status": app.status,
        "updated_at": app.updated_at
    }
