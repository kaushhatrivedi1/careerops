"""
Deterministic fit scoring used by MVP matching endpoints.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


TOKEN_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9\+\#\.\-]{1,}")
STOPWORDS = {
    "and",
    "the",
    "for",
    "with",
    "from",
    "that",
    "this",
    "your",
    "you",
    "our",
    "are",
    "will",
    "have",
    "years",
    "year",
    "experience",
}

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


def _normalize_tokens(text: str) -> list[str]:
    tokens = [t.lower() for t in TOKEN_PATTERN.findall(text or "")]
    return [t for t in tokens if t not in STOPWORDS and len(t) > 2]


def _extract_keywords(text: str, limit: int = 60) -> list[str]:
    token_counts: dict[str, int] = {}
    for token in _normalize_tokens(text):
        token_counts[token] = token_counts.get(token, 0) + 1
    sorted_tokens = sorted(token_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [token for token, _ in sorted_tokens[:limit]]


def _jaccard_similarity(tokens_a: set[str], tokens_b: set[str]) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    inter = tokens_a.intersection(tokens_b)
    union = tokens_a.union(tokens_b)
    if not union:
        return 0.0
    return len(inter) / len(union)


def _ats_risk(resume_text: str, job_keywords: set[str], matched_keywords: set[str]) -> tuple[float, dict[str, Any]]:
    lowered = (resume_text or "").lower()
    penalties: list[str] = []
    risk = 0.0

    for section in REQUIRED_SECTION_HINTS:
        if section not in lowered:
            risk += 0.12
            penalties.append(f"Missing common section: {section}")

    total_words = max(1, len((resume_text or "").split()))
    density = len(matched_keywords) / total_words
    if density < 0.02:
        risk += 0.20
        penalties.append("Low keyword density against job requirements")

    if len(job_keywords) >= 8:
        coverage = len(matched_keywords) / len(job_keywords)
        if coverage < 0.35:
            risk += 0.25
            penalties.append("Low required-skill coverage")

    risk = min(max(risk, 0.0), 1.0)
    return risk, {
        "keyword_density": round(density, 4),
        "penalties": penalties,
    }


def compute_fit_score(resume_text: str, job_text: str) -> ScoreResult:
    resume_tokens = set(_normalize_tokens(resume_text))
    job_keywords_list = _extract_keywords(job_text)
    job_keywords = set(job_keywords_list)

    matched_keywords = resume_tokens.intersection(job_keywords)
    missing_keywords = job_keywords.difference(resume_tokens)

    semantic_score = _jaccard_similarity(resume_tokens, job_keywords)
    keyword_coverage = (len(matched_keywords) / len(job_keywords)) if job_keywords else 0.0
    ats_risk_score, ats_details = _ats_risk(resume_text, job_keywords, matched_keywords)

    fit_index = 100.0 * (
        0.55 * semantic_score
        + 0.35 * keyword_coverage
        + 0.10 * (1.0 - ats_risk_score)
    )

    top_missing = sorted(missing_keywords)[:10]
    top_matched = sorted(matched_keywords)[:10]
    explanation = {
        "formula_version": "v1_deterministic",
        "components": {
            "semantic_score": round(semantic_score, 4),
            "keyword_coverage": round(keyword_coverage, 4),
            "ats_risk_score": round(ats_risk_score, 4),
        },
        "ats_details": ats_details,
        "recommendations": [
            {
                "type": "add_keywords",
                "message": "Add explicit evidence for missing required skills.",
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
        keyword_coverage=round(keyword_coverage, 4),
        ats_risk_score=round(ats_risk_score, 4),
        fit_index=round(max(0.0, min(fit_index, 100.0)), 2),
        explanation=explanation,
        top_missing_keywords=top_missing,
        top_matched_keywords=top_matched,
    )


def build_suggested_resume_draft(resume_text: str, missing_keywords: list[str]) -> str:
    """
    Build a lightweight resume draft suggestion from computed gaps.
    """
    base = (resume_text or "").strip()
    if not missing_keywords:
        return base

    additions = ", ".join(missing_keywords[:8])
    if "skills" in base.lower():
        return f"{base}\n\nTargeted keywords to add evidence for: {additions}"
    return f"{base}\n\nSkills: {additions}"
