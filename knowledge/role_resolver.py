"""
Role Resolution — Zero-Embedding Alias Dictionary & Fallback Logic

Maps free-text role inputs to canonical keys in roles.json using
string matching. Falls back to General_Interview_Mode if unrecognized.
"""

# ── Alias Dictionary ─────────────────────────────────────────────────
# Maps lowercase free-text variations → canonical role keys in roles.json
ROLE_ALIASES: dict[str, str] = {
    # Software Development Engineer
    "software development engineer": "Software_Development_Engineer",
    "software engineer": "Software_Development_Engineer",
    "software developer": "Software_Development_Engineer",
    "software dev": "Software_Development_Engineer",
    "sde": "Software_Development_Engineer",
    "swe": "Software_Development_Engineer",
    "full stack engineer": "Software_Development_Engineer",
    "full stack developer": "Software_Development_Engineer",
    "fullstack engineer": "Software_Development_Engineer",
    "fullstack developer": "Software_Development_Engineer",
    "developer": "Software_Development_Engineer",

    # AI/ML Engineer
    "ai/ml engineer": "AI_ML_Engineer",
    "ai ml engineer": "AI_ML_Engineer",
    "ai engineer": "AI_ML_Engineer",
    "ml engineer": "AI_ML_Engineer",
    "machine learning engineer": "AI_ML_Engineer",
    "machine learning": "AI_ML_Engineer",
    "deep learning engineer": "AI_ML_Engineer",
    "nlp engineer": "AI_ML_Engineer",

    # Backend Engineer
    "backend engineer": "Backend_Engineer",
    "backend developer": "Backend_Engineer",
    "backend dev": "Backend_Engineer",
    "backend": "Backend_Engineer",
    "server engineer": "Backend_Engineer",
    "api engineer": "Backend_Engineer",

    # Frontend Engineer (maps to SDE since no separate role in roles.json)
    "frontend engineer": "Software_Development_Engineer",
    "frontend developer": "Software_Development_Engineer",
    "frontend dev": "Software_Development_Engineer",
    "frontend": "Software_Development_Engineer",
    "ui engineer": "Software_Development_Engineer",
    "react developer": "Software_Development_Engineer",

    # Product Manager
    "product manager": "Product_Manager",
    "pm": "Product_Manager",
    "product owner": "Product_Manager",
    "apm": "Product_Manager",
    "associate product manager": "Product_Manager",
    "technical product manager": "Product_Manager",
    "tpm": "Product_Manager",

    # Data Scientist
    "data scientist": "Data_Scientist",
    "data science": "Data_Scientist",
    "ml scientist": "Data_Scientist",
    "research scientist": "Data_Scientist",

    # Data Analyst (separate role in roles1.json)
    "data analyst": "Data_Analyst",
    "analyst": "Data_Analyst",
    "business analyst": "Data_Analyst",
    "bi analyst": "Data_Analyst",
}

# ── Persona Mapping ──────────────────────────────────────────────────
# Each canonical role gets a distinct interviewer persona
ROLE_PERSONAS: dict[str, str] = {
    "Software_Development_Engineer": "a Senior Engineering Manager at a top-tier tech company",
    "AI_ML_Engineer": "a Principal ML Scientist and hiring manager at a leading AI research lab",
    "Backend_Engineer": "a Staff Backend Engineer and tech lead at a high-scale distributed systems company",
    "Product_Manager": "a VP of Product at a fast-growing SaaS company",
    "Data_Scientist": "a Head of Data Science at a data-driven enterprise",
    "Data_Analyst": "a Senior Analytics Manager at a data-driven enterprise",
    "General_Interview_Mode": "a seasoned Senior Hiring Manager at a technology company",
}


def resolve_role(raw_input: str) -> tuple[str, bool]:
    """
    Resolve free-text role input to a canonical role key.

    Returns:
        (canonical_role, was_matched): Tuple of the resolved role key
        and whether it was an exact/fuzzy match (True) or fallback (False).
    """
    normalized = raw_input.strip().lower()

    # Exact match
    if normalized in ROLE_ALIASES:
        return ROLE_ALIASES[normalized], True

    # Substring match — check if any alias is contained in the input or vice versa
    for alias, canonical in ROLE_ALIASES.items():
        if alias in normalized or normalized in alias:
            return canonical, True

    # No match → fallback
    return "General_Interview_Mode", False


def get_persona(canonical_role: str) -> str:
    """Return the interviewer persona string for a given canonical role."""
    return ROLE_PERSONAS.get(canonical_role, ROLE_PERSONAS["General_Interview_Mode"])
