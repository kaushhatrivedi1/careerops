"""
ESCO-based skill extraction using spaCy PhraseMatcher.

On first use, downloads the ESCO skills dataset (~13k skills across all domains)
from the EU's official open data portal and caches it locally.
Subsequent runs load from cache.
"""
from __future__ import annotations

import csv
import io
import logging
import os
from functools import lru_cache
from pathlib import Path

import httpx
import spacy
from spacy.matcher import PhraseMatcher

logger = logging.getLogger(__name__)

# Cache location — sits next to this file
_CACHE_DIR = Path(__file__).parent / ".esco_cache"
_SKILLS_CACHE = _CACHE_DIR / "skills.txt"

# ESCO v1.2 skills CSV (English labels + alternative labels)
# Direct download from EU open data portal
_ESCO_CSV_URL = (
    "https://esco.ec.europa.eu/sites/default/files/Exports/"
    "skills_en.csv"
)

# Fallback: smaller curated list if ESCO download fails
_FALLBACK_SKILLS = [
    # Languages
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Go", "Rust",
    "Swift", "Kotlin", "Scala", "Ruby", "PHP", "R", "MATLAB", "Bash", "SQL",
    # Frontend
    "React", "Angular", "Vue.js", "Next.js", "HTML", "CSS", "Sass", "Redux",
    "GraphQL", "REST API", "Tailwind CSS", "Bootstrap", "jQuery",
    # Backend / infra
    "Node.js", "Django", "FastAPI", "Flask", "Spring Boot", "Express.js",
    "Docker", "Kubernetes", "Terraform", "Ansible", "Jenkins", "CI/CD",
    "Linux", "Unix", "Nginx", "Apache",
    # Cloud
    "AWS", "Azure", "GCP", "Google Cloud", "Amazon Web Services",
    "S3", "EC2", "Lambda", "CloudFormation",
    # Databases
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch",
    "Cassandra", "SQLite", "DynamoDB", "Oracle", "SQL Server",
    # Data / ML
    "Machine Learning", "Deep Learning", "NLP", "Computer Vision",
    "TensorFlow", "PyTorch", "scikit-learn", "Pandas", "NumPy",
    "Tableau", "Power BI", "Spark", "Hadoop", "Kafka", "Airflow",
    "Data Analysis", "Data Science", "Data Engineering", "ETL",
    # Methodologies
    "Agile", "Scrum", "Kanban", "DevOps", "Test Driven Development",
    "Microservices", "System Design", "Object Oriented Programming",
    "Functional Programming", "Git", "GitHub", "JIRA",
    # Finance
    "Financial Modeling", "Valuation", "Excel", "Bloomberg Terminal",
    "Portfolio Management", "Risk Management", "Equity Research",
    "Investment Banking", "Private Equity", "IFRS", "GAAP",
    "Accounting", "Auditing", "Tax", "Derivatives", "Fixed Income",
    # Marketing
    "SEO", "SEM", "Google Analytics", "Google Ads", "Facebook Ads",
    "Content Marketing", "Email Marketing", "A/B Testing", "CRM",
    "Salesforce", "HubSpot", "Marketo", "Brand Management",
    "Market Research", "Copywriting", "Social Media Marketing",
    # Design
    "Figma", "Sketch", "Adobe XD", "Photoshop", "Illustrator",
    "UX Design", "UI Design", "User Research", "Prototyping",
    "Wireframing", "Design Systems", "Accessibility",
    # Healthcare
    "HIPAA", "Electronic Health Records", "Epic", "Patient Care",
    "Clinical Research", "Medical Coding", "ICD-10", "CPT Coding",
    "Nursing", "Pharmacology", "Medical Terminology",
    # Operations / management
    "Project Management", "Product Management", "Stakeholder Management",
    "Budget Management", "Supply Chain", "Logistics", "Procurement",
    "Six Sigma", "Lean", "Process Improvement", "Operations Management",
    "Change Management", "Strategic Planning", "Business Analysis",
    # Soft skills that get listed as requirements
    "Communication", "Leadership", "Team Management", "Mentoring",
    "Problem Solving", "Analytical Thinking", "Critical Thinking",
    "Collaboration", "Cross-functional Collaboration",
]


def _download_esco_skills() -> list[str]:
    """Download ESCO skills CSV and extract preferred + alternative labels."""
    logger.info("Downloading ESCO skills dataset...")
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.get(_ESCO_CSV_URL)
            resp.raise_for_status()
        content = resp.text
    except Exception as e:
        logger.warning(f"ESCO download failed ({e}), using fallback skill list")
        return _FALLBACK_SKILLS

    skills: set[str] = set()
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        # preferred label
        label = (row.get("preferredLabel") or row.get("preferred label") or "").strip()
        if label:
            skills.add(label)
        # alternative labels (pipe or comma separated)
        alt = row.get("altLabels") or row.get("alternativeLabels") or ""
        for a in alt.replace("|", "\n").splitlines():
            a = a.strip()
            if a:
                skills.add(a)

    if not skills:
        logger.warning("ESCO CSV parsed but empty — using fallback skill list")
        return _FALLBACK_SKILLS

    logger.info(f"Loaded {len(skills)} ESCO skills")
    return sorted(skills)


def _load_skills() -> list[str]:
    """Load skills from cache, or download and cache if missing."""
    _CACHE_DIR.mkdir(exist_ok=True)
    if _SKILLS_CACHE.exists():
        skills = [l.strip() for l in _SKILLS_CACHE.read_text().splitlines() if l.strip()]
        if skills:
            return skills

    skills = _download_esco_skills()
    _SKILLS_CACHE.write_text("\n".join(skills))
    return skills


@lru_cache(maxsize=1)
def _get_matcher() -> tuple[spacy.language.Language, PhraseMatcher]:
    """Build and cache the spaCy PhraseMatcher over the full skill list."""
    nlp = spacy.load("en_core_web_sm", disable=["ner", "parser"])
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")

    skills = _load_skills()
    # Build phrase patterns in batches for speed
    batch_size = 500
    for i in range(0, len(skills), batch_size):
        batch = skills[i : i + batch_size]
        patterns = list(nlp.pipe(batch))
        matcher.add("SKILL", patterns)

    return nlp, matcher


def extract_skills(text: str) -> list[str]:
    """
    Extract skill mentions from text using ESCO taxonomy + spaCy PhraseMatcher.
    Returns a deduplicated list of matched skill labels (lowercased for comparison).
    """
    if not text:
        return []

    nlp, matcher = _get_matcher()
    doc = nlp(text[:50_000])  # cap to avoid memory issues on huge docs
    matches = matcher(doc)

    seen: set[str] = set()
    result: list[str] = []
    for _, start, end in matches:
        span_text = doc[start:end].text
        key = span_text.lower()
        if key not in seen:
            seen.add(key)
            result.append(span_text)

    return result
