"""
EvidenceSource, Claim, and Event models
"""
from sqlalchemy import Column, String, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship
import uuid
from app.db.session import Base
from datetime import datetime


evidence_type = ENUM("github", "document", "link", "manual", name="evidence_type", create_type=False)


class EvidenceSource(Base):
    __tablename__ = "evidence_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(evidence_type, nullable=False)
    url = Column(String)
    file_url = Column(String)
    raw_text = Column(Text)
    metadata_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User", back_populates="evidence_sources")
    claims = relationship("Claim", back_populates="evidence_source", cascade="all, delete-orphan")


class Claim(Base):
    __tablename__ = "claims"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    claim_text = Column(Text, nullable=False)
    evidence_source_id = Column(UUID(as_uuid=True), ForeignKey("evidence_sources.id", ondelete="SET NULL"), nullable=True)
    evidence_span_json = Column(JSON)
    verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    evidence_source = relationship("EvidenceSource", back_populates="claims")


class Event(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String, nullable=False)
    payload_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
