"""
Evidence and Claims models
"""
from sqlalchemy import Column, String, DateTime, Text, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID, ENUM
import uuid
from app.db.session import Base
from datetime import datetime


# Evidence type enum
evidence_type = ENUM('github', 'document', 'link', 'manual', name='evidence_type')


class EvidenceSource(Base):
    __tablename__ = "evidence_sources"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    type = Column(evidence_type, nullable=False)
    url = Column(String)
    file_url = Column(String)
    raw_text = Column(Text)
    metadata_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="evidence_sources")
    claims = relationship("Claim", back_populates="evidence_source", cascade="all, delete-orphan")


class Claim(Base):
    __tablename__ = "claims"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    claim_text = Column(Text, nullable=False)
    evidence_source_id = Column(UUID(as_uuid=True))
    evidence_span_json = Column(JSON)  # offsets, quote, etc.
    verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    evidence_source = relationship("EvidenceSource", back_populates="claims")


class Event(Base):
    __tablename__ = "events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True))
    event_type = Column(String, nullable=False)  # e.g., RESUME_UPLOADED, MATCH_COMPUTED
    payload_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

