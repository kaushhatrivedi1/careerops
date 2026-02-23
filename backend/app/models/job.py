"""
Job model
"""
from sqlalchemy import Column, String, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.db.session import Base
from datetime import datetime


class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String)  # e.g., "manual", "kaggle", "indeed"
    company = Column(String)
    title = Column(String)
    location = Column(String)
    jd_text = Column(Text, nullable=False)
    jd_parsed_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    applications = relationship("Application", back_populates="job")
    matches = relationship("Match", back_populates="job")
    documents = relationship("Document", back_populates="job", foreign_keys="Document.job_id")


# Application status enum
application_status = ENUM('saved', 'applied', 'interview', 'offer', 'reject', name='application_status')


class Application(Base):
    __tablename__ = "applications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    resume_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    status = Column(application_status, default='saved')
    applied_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="applications")
    job = relationship("Job", back_populates="applications")
    resume = relationship("Resume", back_populates="applications", foreign_keys="Application.resume_id")


class Match(Base):
    __tablename__ = "matches"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    resume_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Scores
    semantic_score = Column(String)  # Store as string for flexibility
    keyword_coverage = Column(String)
    ats_risk_score = Column(String)
    overall_score = Column(String)
    
    # Explanations
    explanation_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    resume = relationship("Resume", foreign_keys=[resume_id])
    job = relationship("Job", back_populates="matches")

