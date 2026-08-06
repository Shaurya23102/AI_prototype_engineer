"""
Knowledge Loader — In-Memory Triplet Storage

Loads concept triplets from roles1.json at startup for O(1) retrieval.
All focus areas (technical, behavioral, case, mixed) are read directly
from the JSON — no hardcoded fallback lists needed.
Concepts are randomly shuffled at load time for varied interviews.
"""

import json
import random
from pathlib import Path
from typing import Optional


# ── Module-level cache ────────────────────────────────────────────────
_roles_data: Optional[dict] = None


# ── Fallback Concepts ─────────────────────────────────────────────────
# Used ONLY when the role isn't recognized (General_Interview_Mode)
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


def load_roles(roles_path: Optional[str] = None) -> dict:
    """
    Load roles1.json into memory. Caches after first load.

    Args:
        roles_path: Optional explicit path. Defaults to roles1.json in project root.

    Returns:
        Parsed roles dictionary.
    """
    global _roles_data

    if _roles_data is not None:
        return _roles_data

    if roles_path is None:
        roles_path = str(Path(__file__).parent.parent / "roles1.json")

    with open(roles_path, "r", encoding="utf-8") as f:
        _roles_data = json.load(f)

    return _roles_data


def _triplets_to_dicts(triplets: list[list]) -> list[dict]:
    """Convert raw [subject, predicate, object] lists into dicts."""
    return [
        {"subject": t[0], "predicate": t[1], "object": t[2]}
        for t in triplets
    ]


def get_concepts(canonical_role: str, focus_area: str = "technical") -> list[dict]:
    """
    Retrieve concept triplets for a given role and focus area.
    Concepts are randomly shuffled so each interview feels different.

    Args:
        canonical_role: Canonical role key (e.g., 'AI_ML_Engineer').
        focus_area: One of 'technical', 'behavioral', 'case', 'mixed'.

    Returns:
        List of concept dicts with keys: subject, predicate, object.
        Randomly shuffled for variety.
    """
    if _roles_data is None:
        load_roles()

    # General fallback — role not in JSON
    if canonical_role == "General_Interview_Mode":
        concepts = list(GENERAL_CONCEPTS)
        random.shuffle(concepts)
        return concepts

    # Load from roles1.json — all focus areas live in the JSON
    role_data = _roles_data.get("roles", {}).get(canonical_role, {})
    focus_areas = role_data.get("focus_areas", {})

    # Fetch the requested focus area directly from JSON
    triplets = focus_areas.get(focus_area, [])
    concepts = _triplets_to_dicts(triplets)

    # If requested focus area doesn't exist, fall back to technical
    if not concepts:
        triplets = focus_areas.get("technical", [])
        concepts = _triplets_to_dicts(triplets)

    # If still empty, use general fallback
    if not concepts:
        concepts = list(GENERAL_CONCEPTS)

    # Randomly shuffle for variety across sessions
    random.shuffle(concepts)
    return concepts


def format_concept(concept: dict) -> str:
    """Format a concept triplet as a readable string."""
    return f"{concept['subject']} -> {concept['predicate']} -> {concept['object']}"


def format_concept_list(concepts: list[dict]) -> str:
    """Format a list of concepts as a numbered string."""
    if not concepts:
        return "(none)"
    return "\n".join(
        f"  {i+1}. {format_concept(c)}" for i, c in enumerate(concepts)
    )
