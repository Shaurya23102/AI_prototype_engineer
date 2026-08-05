"""
Knowledge Loader — In-Memory Triplet Storage

Loads concept triplets from roles.json at startup for O(1) retrieval.
Provides fallback concepts for General_Interview_Mode and behavioral focus areas.
"""

import json
from pathlib import Path
from typing import Optional


# ── Module-level cache ────────────────────────────────────────────────
_roles_data: Optional[dict] = None


# ── Fallback Concepts ─────────────────────────────────────────────────
# Used when the role isn't recognized (General_Interview_Mode)
GENERAL_CONCEPTS: list[dict] = [
    {"subject": "Problem Decomposition", "predicate": "breaks_complex_problems_into", "object": "Manageable Sub-Problems"},
    {"subject": "System Design Fundamentals", "predicate": "architect_scalable_systems_using", "object": "Layered Abstraction Patterns"},
    {"subject": "Data Structures & Algorithms", "predicate": "optimize_computational_efficiency_via", "object": "Appropriate Structure Selection"},
    {"subject": "Communication Skills", "predicate": "articulates_technical_concepts_through", "object": "Clear Structured Explanations"},
    {"subject": "Trade-off Analysis", "predicate": "evaluate_engineering_decisions_across", "object": "Performance-Cost-Complexity Axes"},
    {"subject": "Debugging & Root Cause Analysis", "predicate": "isolate_failures_using", "object": "Systematic Elimination Methods"},
    {"subject": "Code Quality & Testing", "predicate": "ensure_reliability_through", "object": "Automated Test Strategies"},
    {"subject": "Project Ownership", "predicate": "drive_outcomes_by_managing", "object": "Scope-Timeline-Quality Constraints"},
]

# Behavioral concepts — used for behavioral focus area
BEHAVIORAL_CONCEPTS: list[dict] = [
    {"subject": "Leadership & Influence", "predicate": "drive_team_outcomes_through", "object": "Cross-Functional Collaboration"},
    {"subject": "Conflict Resolution", "predicate": "navigate_disagreements_using", "object": "Empathetic Active Listening"},
    {"subject": "Failure & Learning", "predicate": "demonstrate_growth_mindset_through", "object": "Post-Mortem Reflection"},
    {"subject": "Ambiguity Tolerance", "predicate": "make_progress_despite", "object": "Incomplete Information"},
    {"subject": "Ownership & Accountability", "predicate": "deliver_results_by_taking", "object": "End-to-End Responsibility"},
    {"subject": "Stakeholder Management", "predicate": "align_competing_priorities_across", "object": "Diverse Organizational Interests"},
    {"subject": "Time Management", "predicate": "prioritize_high_impact_work_using", "object": "Structured Prioritization Frameworks"},
    {"subject": "Adaptability", "predicate": "respond_effectively_to", "object": "Changing Requirements and Contexts"},
]


def load_roles(roles_path: Optional[str] = None) -> dict:
    """
    Load roles.json into memory. Caches after first load.

    Args:
        roles_path: Optional explicit path. Defaults to roles.json in project root.

    Returns:
        Parsed roles dictionary.
    """
    global _roles_data

    if _roles_data is not None:
        return _roles_data

    if roles_path is None:
        roles_path = str(Path(__file__).parent.parent / "roles.json")

    with open(roles_path, "r", encoding="utf-8") as f:
        _roles_data = json.load(f)

    return _roles_data


def get_concepts(canonical_role: str, focus_area: str = "technical") -> list[dict]:
    """
    Retrieve concept triplets for a given role and focus area.

    Args:
        canonical_role: Canonical role key (e.g., 'AI_ML_Engineer').
        focus_area: One of 'technical', 'behavioral', 'mixed'.

    Returns:
        List of concept dicts with keys: subject, predicate, object.
    """
    if _roles_data is None:
        load_roles()

    technical_concepts = []
    behavioral_concepts = list(BEHAVIORAL_CONCEPTS)

    # Load technical concepts from roles.json
    if canonical_role == "General_Interview_Mode":
        technical_concepts = list(GENERAL_CONCEPTS)
    else:
        role_data = _roles_data.get("roles", {}).get(canonical_role, {})
        triplets = role_data.get("focus_areas", {}).get("technical", [])
        technical_concepts = [
            {"subject": t[0], "predicate": t[1], "object": t[2]}
            for t in triplets
        ]
        # Fallback if role exists but has no concepts
        if not technical_concepts:
            technical_concepts = list(GENERAL_CONCEPTS)

    # Select based on focus area
    if focus_area == "technical":
        return technical_concepts
    elif focus_area == "behavioral":
        return behavioral_concepts
    elif focus_area == "mixed":
        # Interleave: take first 4-5 technical + first 3-4 behavioral
        mixed = technical_concepts[:5] + behavioral_concepts[:3]
        return mixed
    else:
        # Default to technical
        return technical_concepts


def format_concept(concept: dict) -> str:
    """Format a concept triplet as a readable string."""
    return f"{concept['subject']} → {concept['predicate']} → {concept['object']}"


def format_concept_list(concepts: list[dict]) -> str:
    """Format a list of concepts as a numbered string."""
    if not concepts:
        return "(none)"
    return "\n".join(
        f"  {i+1}. {format_concept(c)}" for i, c in enumerate(concepts)
    )
