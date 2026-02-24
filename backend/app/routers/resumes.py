"""
Resumes router
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.db.session import get_db
from app.models.resume import Resume
from app.models.user import User
from app.core.security import get_authenticated_user
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


class ResumeCreate(BaseModel):
    version_tag: str = "v1"


class ResumeResponse(BaseModel):
    id: str
    user_id: str
    version_tag: str
    file_url: str
    created_at: datetime


@router.post("/", response_model=ResumeResponse)
async def create_resume(
    file: UploadFile = File(...),
    version_tag: str = "v1",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Upload a new resume"""
    # TODO: Upload file to MinIO/S3
    file_url = f"resumes/{uuid.uuid4()}-{file.filename}"
    
    resume = Resume(
        user_id=current_user.id,
        version_tag=version_tag,
        file_url=file_url,
        raw_text="",  # TODO: Extract text from file
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    
    return ResumeResponse(
        id=str(resume.id),
        user_id=str(resume.user_id),
        version_tag=resume.version_tag,
        file_url=resume.file_url,
        created_at=resume.created_at
    )


@router.get("/")
async def list_resumes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List all resumes for a user"""
    from sqlalchemy import select
    result = await db.execute(select(Resume).where(Resume.user_id == current_user.id))
    resumes = result.scalars().all()
    
    return {
        "resumes": [
            {
                "id": str(r.id),
                "user_id": str(r.user_id),
                "version_tag": r.version_tag,
                "file_url": r.file_url,
                "created_at": r.created_at
            }
            for r in resumes
        ]
    }


@router.get("/{resume_id}")
async def get_resume(
    resume_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Get resume by ID"""
    resume = await db.get(Resume, resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    if str(resume.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Forbidden")
    
    return {
        "id": str(resume.id),
        "user_id": str(resume.user_id),
        "version_tag": resume.version_tag,
        "file_url": resume.file_url,
        "raw_text": resume.raw_text,
        "parsed_json": resume.parsed_json,
        "created_at": resume.created_at
    }


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Delete resume"""
    resume = await db.get(Resume, resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    if str(resume.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Forbidden")
    
    await db.delete(resume)
    await db.commit()
    
    return {"message": "Resume deleted successfully"}
