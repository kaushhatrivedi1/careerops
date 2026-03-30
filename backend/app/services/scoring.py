"""
Fit scoring:
1. Extract skills from JD using ESCO taxonomy + spaCy PhraseMatcher
2. Extract skills from resume the same way
3. Intersect → matched skills, difference → missing skills
4. Semantic score: full-doc cosine similarity (background signal)
5. Fit index = 60% skill coverage + 30% semantic + 10% ATS
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np

from app.services.skills import extract_skills


REQUIRED_SECTION_HINTS = ("experience", "skills", "education")


@dataclass
class ScoreResult:
    semantic_score: float
    keyword_coverage: float
    ats_risk_score: float
    fit_index: float
    explanation: dict[str, Any]
    top_missing_keywords: list[str]
    top_matched_keywords: list[str]


@lru_cache(maxsize=1)
def _get_embedding_model():
    from sentence_transformers import SentenceTransformer
    from app.core.config import settings
    return SentenceTransformer(settings.EMBEDDING_MODEL_NAME)


def _embedding_cosine_similarity(text_a: str, text_b: str) -> float:
    model = _get_embedding_model()
    emb_a, emb_b = model.encode(
        [text_a or "", text_b or ""],
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return float(max(0.0, min(float(np.dot(emb_a, emb_b)), 1.0)))


def _ats_risk(
    resume_text: str,
    total_skills: int,
    matched_count: int,
) -> tuple[float, dict[str, Any]]:
    lowered = (resume_text or "").lower()
    penalties: list[str] = []
    risk = 0.0

    for section in REQUIRED_SECTION_HINTS:
        if section not in lowered:
            risk += 0.12
            penalties.append(f"Missing common section: {section}")

    if total_skills >= 5:
        coverage = matched_count / total_skills
        if coverage < 0.35:
            risk += 0.25
            penalties.append("Low skill coverage of job requirements")
        elif coverage < 0.60:
            risk += 0.10
            penalties.append("Moderate skill coverage of job requirements")

    risk = min(max(risk, 0.0), 1.0)
    return risk, {"penalties": penalties}


def compute_fit_score(resume_text: str, job_text: str) -> ScoreResult:
    # 1. Extract skills from both documents
    jd_skills_raw = extract_skills(job_text)
    resume_skills_raw = extract_skills(resume_text)

    jd_skills_lower = {s.lower(): s for s in jd_skills_raw}
    resume_skills_lower = {s.lower() for s in resume_skills_raw}

    matched_skills = [
        label for key, label in jd_skills_lower.items()
        if key in resume_skills_lower
    ]
    missing_skills = [
        label for key, label in jd_skills_lower.items()
        if key not in resume_skills_lower
    ]

    total = len(matched_skills) + len(missing_skills)
    skill_coverage = len(matched_skills) / total if total > 0 else 0.0

    # 2. Full-doc semantic similarity (background signal — same domain check)
    semantic_score = _embedding_cosine_similarity(resume_text, job_text)

    # 3. ATS risk
    ats_risk_score, ats_details = _ats_risk(resume_text, total, len(matched_skills))

    # 4. Fit index
    # 60% skill coverage: primary signal — actual skill gap
    # 30% semantic: general topical alignment
    # 10% ATS: structural penalty
    fit_index = 100.0 * (
        0.60 * skill_coverage
        + 0.30 * semantic_score
        + 0.10 * (1.0 - ats_risk_score)
    )

    top_missing = missing_skills[:10]
    top_matched = matched_skills[:10]

    explanation = {
        "formula_version": "v6_esco_skills",
        "components": {
            "semantic_score": round(semantic_score, 4),
            "skill_coverage": round(skill_coverage, 4),
            "ats_risk_score": round(ats_risk_score, 4),
        },
        "skill_stats": {
            "jd_skills_found": total,
            "matched": len(matched_skills),
            "missing": len(missing_skills),
            "resume_skills_found": len(resume_skills_raw),
        },
        "ats_details": ats_details,
        "recommendations": [
            {
                "type": "missing_skills",
                "message": "These skills are required by the job but not found in your resume.",
                "missing_keywords": top_missing[:5],
            },
            {
                "type": "improve_sections",
                "message": "Ensure experience, skills, and education sections are clear ATS-friendly headings.",
            },
        ],
    }

    return ScoreResult(
        semantic_score=round(semantic_score, 4),
        keyword_coverage=round(skill_coverage, 4),
        ats_risk_score=round(ats_risk_score, 4),
        fit_index=round(max(0.0, min(fit_index, 100.0)), 2),
        explanation=explanation,
        top_missing_keywords=top_missing,
        top_matched_keywords=top_matched,
    )


def build_suggested_resume_draft(resume_text: str, missing_keywords: list[str]) -> str:
    base = (resume_text or "").strip()
    if not missing_keywords:
        return base
    additions = "\n".join(f"- {r}" for r in missing_keywords[:8])
    return f"{base}\n\n--- Skills to add to your resume ---\n{additions}"
