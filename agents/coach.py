"""
Coach Agent — Synthesis Engine

Generates a structured Markdown feedback report after the interview,
citing specific transcript moments and providing actionable recommendations.
"""

from pathlib import Path
from groq import Groq

from knowledge.loader import format_concept_list


# ── Prompt Template ───────────────────────────────────────────────────
_PROMPT_TEMPLATE: str | None = None


def _load_prompt_template() -> str:
    """Load the coach system prompt template from disk (cached)."""
    global _PROMPT_TEMPLATE
    if _PROMPT_TEMPLATE is None:
        prompt_path = Path(__file__).parent.parent / "prompts" / "coach_prompt.txt"
        _PROMPT_TEMPLATE = prompt_path.read_text(encoding="utf-8")
    return _PROMPT_TEMPLATE


def _format_transcript(transcript: list[dict]) -> str:
    """Format the full transcript for inclusion in the coach prompt."""
    lines = []
    turn = 0
    for entry in transcript:
        if entry["role"] == "interviewer":
            turn += 1
            lines.append(f"\n**--- Turn {turn} ---**")
            lines.append(f"**Interviewer:** {entry['content']}")
        elif entry["role"] == "candidate":
            lines.append(f"**Candidate:** {entry['content']}")
    return "\n".join(lines)


def _format_evaluations(evaluations: list[dict]) -> str:
    """Format all per-turn evaluations for the coach prompt."""
    lines = []
    for i, eval_data in enumerate(evaluations, 1):
        scores = eval_data.get("scores", {})
        lines.append(f"\n**Turn {i}:**")
        lines.append(f"  - Relevance: {scores.get('relevance', 'N/A')}/10")
        lines.append(f"  - Specificity: {scores.get('specificity', 'N/A')}/10")
        lines.append(f"  - Structure: {scores.get('structure', 'N/A')}/10")
        lines.append(f"  - Confidence: {scores.get('confidence', 'N/A')}/10")
        lines.append(f"  - Rating: {eval_data.get('overall_rating', 'N/A')}")
        lines.append(f"  - Observations: {eval_data.get('key_observations', 'N/A')}")
    return "\n".join(lines)


def generate_report(state, client: Groq, model: str) -> str:
    """
    Generate the final coaching report.

    Args:
        state: Final InterviewState with complete transcript and evaluations.
        client: Groq client instance.
        model: Model identifier string.

    Returns:
        Structured Markdown report string.
    """
    template = _load_prompt_template()

    prompt = template.format(
        role=state.target_role_display,
        focus_area=state.focus_area,
        total_turns=state.current_turn,
        covered_concepts=format_concept_list(state.covered_concepts),
        remaining_concepts=format_concept_list(state.remaining_concepts),
        transcript=_format_transcript(state.transcript),
        evaluations=_format_evaluations(state.evaluations),
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=3000,
            top_p=0.9,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        return _fallback_report(state, str(e))


def _fallback_report(state, error_msg: str) -> str:
    """Generate a basic fallback report if the LLM call fails."""
    avg_scores = {"relevance": 0, "specificity": 0, "structure": 0, "confidence": 0}
    count = len(state.evaluations) or 1

    for eval_data in state.evaluations:
        for key in avg_scores:
            avg_scores[key] += eval_data.get("scores", {}).get(key, 0)

    for key in avg_scores:
        avg_scores[key] = round(avg_scores[key] / count, 1)

    return f"""# 🎯 Mock Interview Feedback Report

## ⚠️ Note
Full AI-generated report unavailable due to an error: {error_msg}

## 📊 Score Summary
- **Turns completed:** {state.current_turn}
- **Avg Relevance:** {avg_scores['relevance']}/10
- **Avg Specificity:** {avg_scores['specificity']}/10
- **Avg Structure:** {avg_scores['structure']}/10
- **Avg Confidence:** {avg_scores['confidence']}/10

## Concepts Covered
{format_concept_list(state.covered_concepts)}

## Concepts Remaining
{format_concept_list(state.remaining_concepts)}

Please re-run the coach report generation or review the per-turn evaluations above for detailed feedback.
"""
