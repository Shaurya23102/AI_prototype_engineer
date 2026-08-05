"""
Orchestrator — Deterministic State Machine

Manages the InterviewState object and implements the routing logic
that drives the multi-agent interview loop.
"""

from dataclasses import dataclass, field
from typing import Optional

from knowledge.role_resolver import resolve_role, get_persona
from knowledge.loader import load_roles, get_concepts


# ── Interview State ───────────────────────────────────────────────────

@dataclass
class InterviewState:
    """
    Central state object that drives the entire interview workflow.

    All agents read from and write to this state. The orchestrator
    is the ONLY component that mutates it.
    """
    # ── Intake Fields ─────────────────────────────────────────────
    target_role_raw: str                              # User's original input
    target_role_canonical: str                        # Resolved canonical key
    target_role_display: str                          # Display name for prompts
    role_was_matched: bool                            # True if role was recognized
    background: str                                   # Candidate background snippet
    focus_area: str                                   # technical / behavioral / mixed
    persona: str                                      # Interviewer persona string

    # ── Concept Tracking ──────────────────────────────────────────
    remaining_concepts: list[dict] = field(default_factory=list)
    covered_concepts: list[dict] = field(default_factory=list)

    # ── Transcript & Evaluations ──────────────────────────────────
    transcript: list[dict] = field(default_factory=list)
    evaluations: list[dict] = field(default_factory=list)

    # ── Turn Management ───────────────────────────────────────────
    current_turn: int = 0
    max_turns: int = 7


# ── State Factory ─────────────────────────────────────────────────────

def create_state(
    target_role: str,
    background: str,
    focus_area: str,
    max_turns: int = 7,
) -> InterviewState:
    """
    Initialize a fresh InterviewState from user intake inputs.

    Performs role resolution, loads concepts, and sets up the
    initial state for the interview loop.
    """
    # Resolve role → canonical key
    canonical, was_matched = resolve_role(target_role)

    # Display name: clean up canonical key for prompts
    display_name = canonical.replace("_", " ")
    if not was_matched:
        display_name = f"{target_role} (General Mode)"

    # Load concept triplets
    load_roles()  # Ensure roles.json is cached
    concepts = get_concepts(canonical, focus_area)

    # Get interviewer persona
    persona = get_persona(canonical)

    return InterviewState(
        target_role_raw=target_role,
        target_role_canonical=canonical,
        target_role_display=display_name,
        role_was_matched=was_matched,
        background=background,
        focus_area=focus_area,
        persona=persona,
        remaining_concepts=list(concepts),
        covered_concepts=[],
        max_turns=max_turns,
    )


# ── State Mutations ──────────────────────────────────────────────────

def add_to_transcript(state: InterviewState, role: str, content: str) -> None:
    """
    Append an entry to the interview transcript.

    Args:
        state: Current interview state.
        role: 'interviewer' or 'candidate'.
        content: The spoken text.
    """
    state.transcript.append({
        "role": role,
        "content": content,
        "turn": state.current_turn,
    })


def update_state_after_evaluation(
    state: InterviewState,
    evaluation: dict,
) -> None:
    """
    Update the state based on the evaluator's output.

    Moves successfully covered concepts from remaining → covered,
    increments the turn counter, and stores the evaluation.
    """
    state.evaluations.append(evaluation)

    # Move covered concepts
    covered_subjects = set(evaluation.get("concepts_covered", []))
    if covered_subjects:
        newly_covered = []
        still_remaining = []
        for concept in state.remaining_concepts:
            if concept["subject"] in covered_subjects:
                newly_covered.append(concept)
            else:
                still_remaining.append(concept)
        state.covered_concepts.extend(newly_covered)
        state.remaining_concepts = still_remaining

    # Increment turn
    state.current_turn += 1


# ── Routing Logic ─────────────────────────────────────────────────────

def should_continue(state: InterviewState) -> bool:
    """
    Determine whether the interview loop should continue.

    Exit conditions:
    1. Turn count >= max_turns (default 7)
    2. All concepts exhausted (remaining_concepts is empty)

    Returns:
        True if the interview should continue, False to exit.
    """
    if state.current_turn >= state.max_turns:
        return False
    if len(state.remaining_concepts) == 0:
        return False
    return True


def get_exit_reason(state: InterviewState) -> str:
    """Return a human-readable reason for why the interview ended."""
    if state.current_turn >= state.max_turns:
        return f"Maximum turns reached ({state.max_turns} turns)"
    if len(state.remaining_concepts) == 0:
        return "All concepts have been covered"
    return "Interview completed"
