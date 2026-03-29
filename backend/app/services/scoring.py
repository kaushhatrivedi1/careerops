"""
Fit scoring: semantic similarity via sentence-transformers + keyword/ATS signals.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np


TOKEN_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9\+\#\.\-]+")

# Common English words that are not skills or meaningful job keywords
STOPWORDS = {
    # articles / conjunctions / prepositions
    "and", "the", "for", "with", "from", "that", "this", "into",
    "over", "under", "about", "above", "after", "before", "between",
    "through", "during", "without", "within", "along", "following",
    "across", "behind", "beyond", "plus", "except", "but", "nor",
    "yet", "both", "either", "neither", "each", "few", "more",
    "most", "other", "some", "such", "than", "too", "very",
    # pronouns / determiners
    "you", "your", "our", "their", "they", "them", "its", "his",
    "her", "who", "what", "which", "where", "when", "how", "all",
    "any", "every", "these", "those", "then", "there", "here",
    # common verbs
    "are", "was", "were", "has", "have", "had", "will", "would",
    "could", "should", "may", "might", "shall", "can", "must",
    "being", "been", "does", "did", "doing", "get", "got", "gets",
    "make", "made", "makes", "take", "taken", "takes", "come",
    "goes", "went", "gone", "give", "given", "gives", "use", "used",
    "using", "uses", "apply", "applied", "applies", "ensure", "need",
    "needs", "help", "helps", "want", "include", "includes", "work",
    "works", "worked", "provide", "provides", "support", "supports",
    "create", "build", "drive", "define", "maintain", "manage",
    # common adjectives / adverbs
    "new", "also", "just", "only", "back", "away", "best", "good",
    "great", "high", "large", "long", "low", "next", "old", "own",
    "same", "small", "well", "able", "always", "never", "often",
    "real", "right", "still", "true", "full", "strong", "fast",
    # job-posting filler words
    "we", "not", "are", "role", "team", "join", "based", "across",
    "awards", "look", "looking", "job", "jobs", "hire", "hiring",
    "position", "opportunity", "opportunities", "candidate",
    "candidates", "company", "business", "people", "person",
    "please", "send", "email", "apply", "application", "submit",
    "resume", "cover", "letter", "requirements", "qualifications",
    "preferred", "required", "must", "plus", "bonus",
    # time / quantity words
    "year", "years", "month", "months", "day", "days", "time",
    "times", "many", "much", "number", "lot", "lots", "part",
    "way", "ways", "type", "types", "level", "levels", "range",
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


@lru_cache(maxsize=1)
def _get_embedding_model():
    from sentence_transformers import SentenceTransformer
    from app.core.config import settings
    return SentenceTransformer(settings.EMBEDDING_MODEL_NAME)


def _embedding_cosine_similarity(text_a: str, text_b: str) -> float:
    """Encode both texts and return cosine similarity in [0, 1]."""
    model = _get_embedding_model()
    emb_a, emb_b = model.encode(
        [text_a or "", text_b or ""],
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    # Dot product of L2-normalised vectors == cosine similarity
    score = float(np.dot(emb_a, emb_b))
    return max(0.0, min(score, 1.0))


def _normalize_tokens(text: str) -> list[str]:
    tokens = [t.lower() for t in TOKEN_PATTERN.findall(text or "")]
    return [t for t in tokens if t not in STOPWORDS and len(t) > 3]


def _extract_keywords(text: str, limit: int = 60) -> list[str]:
    token_counts: dict[str, int] = {}
    for token in _normalize_tokens(text):
        token_counts[token] = token_counts.get(token, 0) + 1
    sorted_tokens = sorted(token_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [token for token, _ in sorted_tokens[:limit]]


def _ats_risk(
    resume_text: str,
    job_keywords: set[str],
    matched_keywords: set[str],
) -> tuple[float, dict[str, Any]]:
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
    return risk, {"keyword_density": round(density, 4), "penalties": penalties}


def compute_fit_score(resume_text: str, job_text: str) -> ScoreResult:
    # Semantic similarity via sentence embeddings (replaces Jaccard)
    semantic_score = _embedding_cosine_similarity(resume_text, job_text)

    # Keyword signals (kept as complementary signal)
    resume_tokens = set(_normalize_tokens(resume_text))
    job_keywords_list = _extract_keywords(job_text)
    job_keywords = set(job_keywords_list)

    matched_keywords = resume_tokens.intersection(job_keywords)
    missing_keywords = job_keywords.difference(resume_tokens)

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
        "formula_version": "v2_embedding",
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
    """Build a lightweight resume draft suggestion from computed gaps."""
    base = (resume_text or "").strip()
    if not missing_keywords:
        return base

    additions = ", ".join(missing_keywords[:8])
    if "skills" in base.lower():
        return f"{base}\n\nTargeted keywords to add evidence for: {additions}"
    return f"{base}\n\nSkills: {additions}"
