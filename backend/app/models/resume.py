"""
Resume model
"""
from sqlalchemy import Column, String, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID, ENUM
import uuid
from app.db.session import Base
from datetime import datetime


class Resume(Base):
    __tablename__ = "resumes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    version_tag = Column(String, default="v1")
    file_url = Column(String)  # MinIO/S3 path
    raw_text = Column(Text)
    parsed_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="resumes")
    applications = relationship("Application", back_populates="resume")
    documents = relationship("Document", back_populates="resume", foreign_keys="Document.resume_id")
    chunks = relationship("Chunk", back_populates="resume", cascade="all, delete-orphan")


# For document owner_type enum
document_owner_type = ENUM('resume', 'job', 'evidence', name='document_owner_type')


class Document(Base):
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_type = Column(document_owner_type, nullable=False)
    owner_id = Column(UUID(as_uuid=True), nullable=False)  # Soft reference
    title = Column(String)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Foreign key to resume (for resume documents)
    resume_id = Column(UUID(as_uuid=True))
    
    # Relationships
    resume = relationship("Resume", back_populates="documents", foreign_keys=[resume_id])
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


# Section type enum
section_type = ENUM('summary', 'experience', 'education', 'skills', 'projects', 'certifications', 'other', name='section_type')


class Chunk(Base):
    __tablename__ = "chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    chunk_index = Column(String, nullable=False)  # Store as string for flexibility
    section = Column(section_type, default='other')
    chunk_text = Column(Text, nullable=False)
    token_count = Column(String)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    document = relationship("Document", back_populates="chunks")
    embeddings = relationship("Embedding", back_populates="chunk", cascade="all, delete-orphan")


class Embedding(Base):
    __tablename__ = "embeddings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chunk_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    model_name = Column(String, nullable=False)
    embedding = Column(String)  # Store as string, pgvector handles it
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    chunk = relationship("Chunk", back_populates="embeddings")

