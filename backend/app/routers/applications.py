"""
Applications router
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.db.session import get_db
from app.models.job import Application, application_status
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
async def create_application(app_data: ApplicationCreate, db: AsyncSession = Depends(get_db)):
    """Create a new application"""
    # TODO: Validate job_id and resume_id exist and belong to user
    
    app = Application(
        user_id="temp-user-id",  # TODO: Get from auth
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
    db: AsyncSession = Depends(get_db)
):
    """List applications for current user"""
    from sqlalchemy import select
    
    user_id = "temp-user-id"  # TODO: Get from auth
    query = select(Application).where(Application.user_id == user_id)
    
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
    db: AsyncSession = Depends(get_db)
):
    """Update application status"""
    app = await db.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
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

