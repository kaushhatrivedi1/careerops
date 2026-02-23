"""
Jobs router
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import uuid

from app.db.session import get_db
from app.models.job import Job
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


class JobCreate(BaseModel):
    source: str = "manual"
    company: str
    title: str
    location: str
    jd_text: str


class JobResponse(BaseModel):
    id: str
    source: str
    company: str
    title: str
    location: str
    created_at: datetime


@router.post("/", response_model=JobResponse)
async def create_job(job_data: JobCreate, db: AsyncSession = Depends(get_db)):
    """Create a new job listing"""
    job = Job(
        source=job_data.source,
        company=job_data.company,
        title=job_data.title,
        location=job_data.location,
        jd_text=job_data.jd_text
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    return JobResponse(
        id=str(job.id),
        source=job.source,
        company=job.company,
        title=job.title,
        location=job.location,
        created_at=job.created_at
    )


@router.get("/")
async def list_jobs(
    company: str = None,
    title: str = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """List jobs with optional filters"""
    from sqlalchemy import select, text
    
    query = select(Job)
    
    if company:
        query = query.where(Job.company.ilike(f"%{company}%"))
    if title:
        query = query.where(Job.title.ilike(f"%{title}%"))
    
    query = query.offset(offset).limit(limit)
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    return {
        "jobs": [
            {
                "id": str(j.id),
                "source": j.source,
                "company": j.company,
                "title": j.title,
                "location": j.location,
                "jd_text": j.jd_text[:500] + "..." if j.jd_text and len(j.jd_text) > 500 else j.jd_text,
                "created_at": j.created_at
            }
            for j in jobs
        ],
        "total": len(jobs)
    }


@router.get("/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Get job by ID"""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "id": str(job.id),
        "source": job.source,
        "company": job.company,
        "title": job.title,
        "location": job.location,
        "jd_text": job.jd_text,
        "jd_parsed_json": job.jd_parsed_json,
        "created_at": job.created_at
    }


@router.delete("/{job_id}")
async def delete_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Delete job"""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    await db.delete(job)
    await db.commit()
    
    return {"message": "Job deleted successfully"}

