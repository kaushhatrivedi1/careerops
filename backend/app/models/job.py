"""
Job, Application, and Match models
"""
from sqlalchemy import Column, String, DateTime, Text, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship
import uuid
from app.db.session import Base
from datetime import datetime


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String)
    company = Column(String)
    title = Column(String)
    location = Column(String)
    jd_text = Column(Text, nullable=False)
    jd_parsed_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    applications = relationship("Application", back_populates="job")
    matches = relationship("Match", back_populates="job")


application_status = ENUM("saved", "applied", "interview", "offer", "reject", name="application_status", create_type=False)


class Application(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True, index=True)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(application_status, default="saved")
    applied_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    job_url = Column(Text)
    company = Column(String)
    role = Column(String)
    cv_snapshot_text = Column(Text)
    fit_index = Column(String)
    outcome_reported_at = Column(DateTime(timezone=True))

    user = relationship("User", back_populates="applications")
    job = relationship("Job", back_populates="applications")
    resume = relationship("Resume", back_populates="applications")


class Match(Base):
    __tablename__ = "matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    semantic_score = Column(String)
    keyword_coverage = Column(String)
    ats_risk_score = Column(String)
    overall_score = Column(String)
    explanation_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id])
    resume = relationship("Resume", foreign_keys=[resume_id])
    job = relationship("Job", back_populates="matches")
