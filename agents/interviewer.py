"""
Interviewer Agent — Persona & Dialogue Engine

Generates interview questions driven by the evaluator's direction
and the remaining concept list. Streams plain text, stays in character.
"""

from pathlib import Path
from groq import Groq

from knowledge.loader import format_concept_list


# ── Prompt Template ───────────────────────────────────────────────────
_PROMPT_TEMPLATE: str | None = None


def _load_prompt_template() -> str:
    """Load the interviewer system prompt template from disk (cached)."""
    global _PROMPT_TEMPLATE
    if _PROMPT_TEMPLATE is None:
        prompt_path = Path(__file__).parent.parent / "prompts" / "interviewer_prompt.txt"
        _PROMPT_TEMPLATE = prompt_path.read_text(encoding="utf-8")
    return _PROMPT_TEMPLATE


def _build_system_prompt(state) -> str:
    """
    Build the full system prompt by injecting dynamic state into the template.

    Uses only remaining_concepts to prevent token bloat and repetition.
    """
    template = _load_prompt_template()

    # Determine evaluator direction based on turn number
    if state.current_turn == 0:
        direction = "This is the FIRST turn. Introduce yourself briefly (one sentence) and ask an opening question about the first remaining concept."
    elif state.evaluations:
        last_eval = state.evaluations[-1]
        direction = last_eval.get("interviewer_direction", "Move to the next concept.")
    else:
        direction = "Continue the interview. Pick the next concept from the remaining list."

    # Determine difficulty level
    if state.evaluations:
        recent_scores = [
            e.get("scores", {}).get("relevance", 5)
            for e in state.evaluations[-3:]  # Last 3 turns
        ]
        avg = sum(recent_scores) / len(recent_scores)
        if avg >= 7.5:
            difficulty = "Hard — candidate is performing well. Push with edge cases and trade-offs."
        elif avg >= 5:
            difficulty = "Medium — candidate is at a moderate level. Standard difficulty."
        else:
            difficulty = "Easy — candidate is struggling. Ask more foundational questions."
    else:
        difficulty = "Medium — opening question. Gauge the candidate's level."

    return template.format(
        persona=state.persona,
        role_display=state.target_role_display,
        focus_area=state.focus_area,
        background=state.background or "No background provided.",
        difficulty=difficulty,
        covered_concepts=format_concept_list(state.covered_concepts),
        remaining_concepts=format_concept_list(state.remaining_concepts),
        evaluator_direction=direction,
    )


def _build_messages(state) -> list[dict]:
    """
    Build the message list for the LLM call.

    Includes the system prompt + conversation history so the interviewer
    can maintain natural dialogue flow.
    """
    messages = [{"role": "system", "content": _build_system_prompt(state)}]

    # Add transcript history for conversational continuity
    for entry in state.transcript:
        if entry["role"] == "interviewer":
            messages.append({"role": "assistant", "content": entry["content"]})
        elif entry["role"] == "candidate":
            messages.append({"role": "user", "content": entry["content"]})

    # If no transcript yet, add a nudge to start
    if not state.transcript:
        messages.append({
            "role": "user",
            "content": "Please begin the interview now."
        })

    return messages


def generate_question(state, client: Groq, model: str) -> str:
    """
    Generate the next interview question.

    Args:
        state: Current InterviewState object.
        client: Groq client instance.
        model: Model identifier string.

    Returns:
        The interviewer's question as plain text.
    """
    messages = _build_messages(state)

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.75,
        max_tokens=512,
        top_p=0.9,
    )

    return response.choices[0].message.content.strip()
