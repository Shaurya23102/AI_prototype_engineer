"""
Evaluator Agent — Structured JSON Scoring Engine

Analyzes candidate responses and outputs strict JSON with scores,
concept coverage, and routing instructions for the Interviewer.
"""

import json
from pathlib import Path
from groq import Groq

from knowledge.loader import format_concept_list


# ── Prompt Template ───────────────────────────────────────────────────
_PROMPT_TEMPLATE: str | None = None


def _load_prompt_template() -> str:
    """Load the evaluator system prompt template from disk (cached)."""
    global _PROMPT_TEMPLATE
    if _PROMPT_TEMPLATE is None:
        prompt_path = Path(__file__).parent.parent / "prompts" / "evaluator_prompt.txt"
        _PROMPT_TEMPLATE = prompt_path.read_text(encoding="utf-8")
    return _PROMPT_TEMPLATE


def _build_prompt(question: str, answer: str, state) -> str:
    """Build the full evaluator prompt with injected context."""
    template = _load_prompt_template()

    # Format active concepts (remaining ones the interviewer is probing)
    active_concepts = format_concept_list(state.remaining_concepts[:3])

    return template.format(
        role=state.target_role_display,
        focus_area=state.focus_area,
        turn=state.current_turn,
        active_concepts=active_concepts,
        question=question,
        answer=answer,
    )


def _parse_evaluation(raw_text: str) -> dict:
    """
    Parse the evaluator's JSON output with fallback handling.

    Attempts to extract valid JSON even if the model wraps it in
    markdown code fences or adds extra commentary.
    """
    text = raw_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last fence lines
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
        return _validate_evaluation(parsed)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from mixed text
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start:end])
            return _validate_evaluation(parsed)
        except json.JSONDecodeError:
            pass

    # Complete fallback — return a safe default evaluation
    return _fallback_evaluation()


def _validate_evaluation(parsed: dict) -> dict:
    """Validate and normalize the parsed evaluation dict."""
    # Ensure required keys exist with safe defaults
    scores = parsed.get("scores", {})
    validated = {
        "scores": {
            "relevance": _clamp(scores.get("relevance", 5), 1, 10),
            "specificity": _clamp(scores.get("specificity", 5), 1, 10),
            "structure": _clamp(scores.get("structure", 5), 1, 10),
            "confidence": _clamp(scores.get("confidence", 5), 1, 10),
        },
        "overall_rating": parsed.get("overall_rating", "partial"),
        "concepts_covered": parsed.get("concepts_covered", []),
        "interviewer_direction": parsed.get(
            "interviewer_direction", "Continue with the next concept."
        ),
        "key_observations": parsed.get(
            "key_observations", "Evaluation completed."
        ),
    }

    # Validate overall_rating is one of the expected values
    if validated["overall_rating"] not in ("strong", "partial", "weak"):
        avg = sum(validated["scores"].values()) / 4
        if avg >= 7:
            validated["overall_rating"] = "strong"
        elif avg >= 4.5:
            validated["overall_rating"] = "partial"
        else:
            validated["overall_rating"] = "weak"

    return validated


def _fallback_evaluation() -> dict:
    """Return a safe fallback evaluation when JSON parsing fails entirely."""
    return {
        "scores": {
            "relevance": 5,
            "specificity": 5,
            "structure": 5,
            "confidence": 5,
        },
        "overall_rating": "partial",
        "concepts_covered": [],
        "interviewer_direction": "Continue with the next concept from the remaining list.",
        "key_observations": "Evaluation parsing failed; using default scores.",
    }


def _clamp(value, min_val: int, max_val: int) -> int:
    """Clamp a value to [min_val, max_val], handling type coercion."""
    try:
        return max(min_val, min(max_val, int(value)))
    except (TypeError, ValueError):
        return (min_val + max_val) // 2


def evaluate_response(
    question: str,
    answer: str,
    state,
    client: Groq,
    model: str,
) -> dict:
    """
    Evaluate a candidate's response.

    Args:
        question: The question that was asked.
        answer: The candidate's response text.
        state: Current InterviewState.
        client: Groq client instance.
        model: Model identifier string.

    Returns:
        Validated evaluation dict with scores, rating, concepts, and direction.
    """
    prompt = _build_prompt(question, answer, state)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,       # Low temperature for consistent scoring
            max_tokens=512,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        return _parse_evaluation(raw)

    except Exception as e:
        # On API error, return fallback so the interview can continue
        fallback = _fallback_evaluation()
        fallback["key_observations"] = f"Evaluator error: {str(e)[:100]}"
        return fallback
