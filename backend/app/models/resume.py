"""
Resume, Document, Chunk, and Embedding models
"""
from sqlalchemy import Column, String, DateTime, Text, JSON, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship
import uuid
from app.db.session import Base
from datetime import datetime


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    version_tag = Column(String, default="v1")
    file_url = Column(String)
    raw_text = Column(Text)
    parsed_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User", back_populates="resumes")
    applications = relationship("Application", back_populates="resume")
    documents = relationship("Document", back_populates="resume", foreign_keys="Document.resume_id")


document_owner_type = ENUM("resume", "job", "evidence", name="document_owner_type", create_type=False)


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_type = Column(document_owner_type, nullable=False)
    owner_id = Column(UUID(as_uuid=True), nullable=False)
    title = Column(String)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"))

    resume = relationship("Resume", back_populates="documents", foreign_keys=[resume_id])
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


section_type = ENUM("summary", "experience", "education", "skills", "projects", "certifications", "other", name="section_type", create_type=False)


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    section = Column(section_type, default="other")
    chunk_text = Column(Text, nullable=False)
    token_count = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    document = relationship("Document", back_populates="chunks")
    embeddings = relationship("Embedding", back_populates="chunk", cascade="all, delete-orphan")


class Embedding(Base):
    __tablename__ = "embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False, index=True)
    model_name = Column(String, nullable=False)
    embedding = Column(String)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    chunk = relationship("Chunk", back_populates="embeddings")
