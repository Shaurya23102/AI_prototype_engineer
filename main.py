"""
AI Mock Interview Coach — CLI Entry Point

A multi-agent system that conducts realistic mock interviews and
delivers structured coaching feedback.

Usage:
    python main.py
"""

import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich.rule import Rule
from rich.theme import Theme

from orchestrator import (
    create_state,
    add_to_transcript,
    update_state_after_evaluation,
    should_continue,
    get_exit_reason,
)
from agents.interviewer import generate_question
from agents.evaluator import evaluate_response
from agents.coach import generate_report


# ── Theme & Console Setup ─────────────────────────────────────────────

CUSTOM_THEME = Theme({
    "info": "cyan",
    "success": "green",
    "warning": "yellow",
    "error": "red bold",
    "interviewer": "bold blue",
    "candidate": "bold green",
    "system": "dim",
})

console = Console(theme=CUSTOM_THEME)


# ── Constants ─────────────────────────────────────────────────────────

FOCUS_AREAS = ["technical", "behavioral", "case", "mixed"]


# ── Display Helpers ───────────────────────────────────────────────────

def show_banner():
    """Display the application banner."""
    banner = """
╔══════════════════════════════════════════════════════════╗
║          🎯  AI MOCK INTERVIEW COACH  🎯                ║
║                                                          ║
║   Multi-Agent System • Adaptive Difficulty • Real-Time   ║
║              Scoring • Personalized Coaching             ║
╚══════════════════════════════════════════════════════════╝
"""
    console.print(banner, style="bold cyan")


def show_interviewer_message(message: str, turn: int, max_turns: int):
    """Display the interviewer's question in a styled panel."""
    console.print()
    console.print(Panel(
        message,
        title=f"[interviewer]🎤 Interviewer — Turn {turn}/{max_turns}[/]",
        border_style="blue",
        padding=(1, 2),
    ))


def show_evaluation_summary(evaluation: dict, turn: int):
    """Display a compact evaluation summary after each turn."""
    scores = evaluation.get("scores", {})
    rating = evaluation.get("overall_rating", "unknown")
    observations = evaluation.get("key_observations", "")

    # Rating color
    rating_colors = {"strong": "green", "partial": "yellow", "weak": "red"}
    color = rating_colors.get(rating, "white")

    score_line = (
        f"  Relevance: [bold]{scores.get('relevance', '?')}[/] │ "
        f"Specificity: [bold]{scores.get('specificity', '?')}[/] │ "
        f"Structure: [bold]{scores.get('structure', '?')}[/] │ "
        f"Confidence: [bold]{scores.get('confidence', '?')}[/]  "
        f"  → [{color}]{rating.upper()}[/]"
    )

    console.print()
    console.print(f"  [system]─── Evaluation (Turn {turn}) ───[/]")
    console.print(score_line)
    if observations:
        console.print(f"  [dim]{observations}[/]")
    console.print()


def show_concept_progress(state):
    """Display concept tracking progress."""
    covered = len(state.covered_concepts)
    total = covered + len(state.remaining_concepts)
    filled = int((covered / total) * 20) if total > 0 else 0
    bar = "█" * filled + "░" * (20 - filled)
    console.print(
        f"  [system]Concepts: [{bar}] {covered}/{total} covered[/]"
    )


# ── Intake Phase ──────────────────────────────────────────────────────

def intake() -> dict:
    """Gather candidate information through interactive prompts."""
    console.print(Rule("[bold cyan]Interview Setup[/]"))
    console.print()

    # Target role
    console.print("  [info]What role are you preparing for?[/]")
    console.print("  [dim]Examples: AI/ML Engineer, Product Manager, Backend Developer, "
                  "Data Scientist, Data Analyst, Software Engineer[/]")
    target_role = Prompt.ask("  [bold]Target Role[/]")

    console.print()

    # Background (optional)
    console.print("  [info]Provide a brief background or resume snippet (optional).[/]")
    console.print("  [dim]Press Enter to skip.[/]")
    background = Prompt.ask("  [bold]Background[/]", default="")

    console.print()

    # Focus area
    console.print("  [info]Choose your focus area:[/]")
    for i, area in enumerate(FOCUS_AREAS, 1):
        console.print(f"    {i}. {area.capitalize()}")
    choice = Prompt.ask(
        "  [bold]Focus Area[/]",
        choices=["1", "2", "3", "4", "technical", "behavioral", "case", "mixed"],
        default="1",
    )
    # Map numeric choices to names
    focus_map = {"1": "technical", "2": "behavioral", "3": "case", "4": "mixed"}
    focus_area = focus_map.get(choice, choice)

    return {
        "target_role": target_role,
        "background": background,
        "focus_area": focus_area,
    }


# ── Main Interview Loop ──────────────────────────────────────────────

def run_interview():
    """Execute the full interview workflow."""

    # Load environment
    load_dotenv(Path(__file__).parent / ".env")
    api_key = os.getenv("GROQ_API_KEY")
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    max_turns = int(os.getenv("MAX_TURNS", "7"))

    if not api_key:
        console.print("[error]ERROR: GROQ_API_KEY not found.[/]")
        console.print("Set it in .env or as an environment variable.")
        sys.exit(1)

    # Initialize Groq client
    client = Groq(api_key=api_key)

    # Show banner
    show_banner()

    # Intake
    inputs = intake()

    # Create state
    state = create_state(
        target_role=inputs["target_role"],
        background=inputs["background"],
        focus_area=inputs["focus_area"],
        max_turns=max_turns,
    )

    # Show role resolution result
    console.print()
    console.print(Rule("[bold cyan]Interview Beginning[/]"))
    if state.role_was_matched:
        console.print(
            f"  [success]✓ Role matched:[/] {state.target_role_display}"
        )
    else:
        console.print(
            f"  [warning]⚠ Role not recognized. Using General Interview Mode.[/]"
        )
    console.print(
        f"  [info]Interviewer persona:[/] {state.persona}"
    )
    console.print(
        f"  [info]Concepts loaded:[/] {len(state.remaining_concepts)} "
        f"| Focus: {state.focus_area} | Max turns: {state.max_turns}"
    )
    console.print()

    # ── Interview Loop ────────────────────────────────────────────
    while should_continue(state):
        # 1. Interviewer generates question
        console.print("[dim]  ⏳ Interviewer is preparing a question...[/]")
        try:
            question = generate_question(state, client, model)
        except Exception as e:
            console.print(f"[error]  Interviewer error: {e}[/]")
            break

        add_to_transcript(state, "interviewer", question)
        show_interviewer_message(question, state.current_turn + 1, state.max_turns)

        # 2. Candidate responds
        console.print()
        try:
            answer = Prompt.ask("[bold green]  Your Answer[/]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[warning]  Interview interrupted by candidate.[/]")
            break

        if not answer.strip():
            answer = "I don't know."

        add_to_transcript(state, "candidate", answer)

        # 3. Evaluator scores the response
        console.print("[dim]  ⏳ Evaluating your response...[/]")
        try:
            evaluation = evaluate_response(question, answer, state, client, model)
        except Exception as e:
            console.print(f"[error]  Evaluator error: {e}[/]")
            evaluation = {
                "scores": {"relevance": 5, "specificity": 5, "structure": 5, "confidence": 5},
                "overall_rating": "partial",
                "concepts_covered": [],
                "interviewer_direction": "Continue with the next concept.",
                "key_observations": f"Evaluation error: {str(e)[:80]}",
            }

        # 4. Update state
        update_state_after_evaluation(state, evaluation)
        show_evaluation_summary(evaluation, state.current_turn)
        show_concept_progress(state)

    # ── Exit ──────────────────────────────────────────────────────
    exit_reason = get_exit_reason(state)
    console.print()
    console.print(Rule("[bold cyan]Interview Complete[/]"))
    console.print(f"  [info]Reason:[/] {exit_reason}")
    console.print(f"  [info]Turns completed:[/] {state.current_turn}")
    console.print(
        f"  [info]Concepts covered:[/] {len(state.covered_concepts)} / "
        f"{len(state.covered_concepts) + len(state.remaining_concepts)}"
    )
    console.print()

    # ── Coach Report ──────────────────────────────────────────────
    if state.current_turn > 0:
        console.print("[dim]  ⏳ Generating your personalized coaching report...[/]")
        console.print()

        try:
            report = generate_report(state, client, model)
        except Exception as e:
            console.print(f"[error]  Coach error: {e}[/]")
            report = f"# Error\nCoach report generation failed: {e}"

        # Display report
        console.print(Panel(
            Markdown(report),
            title="[bold magenta]📋 Coaching Report[/]",
            border_style="magenta",
            padding=(1, 2),
        ))

        # Save report to file
        report_path = Path(__file__).parent / "last_interview_report2.md"
        report_path.write_text(report, encoding="utf-8")
        console.print(
            f"\n  [success]✓ Report saved to:[/] {report_path}"
        )

        # Save full transcript
        transcript_path = Path(__file__).parent / "last_interview_transcript2.md"
        transcript_lines = [f"# Interview Transcript — {state.target_role_display}\n"]
        transcript_lines.append(f"Focus: {state.focus_area} | Turns: {state.current_turn}\n")
        turn_num = 0
        for entry in state.transcript:
            if entry["role"] == "interviewer":
                turn_num += 1
                transcript_lines.append(f"\n## Turn {turn_num}\n")
                transcript_lines.append(f"**Interviewer:** {entry['content']}\n")
            elif entry["role"] == "candidate":
                transcript_lines.append(f"**Candidate:** {entry['content']}\n")
        # Append evaluations
        transcript_lines.append("\n## Per-Turn Evaluations\n")
        for i, eval_data in enumerate(state.evaluations, 1):
            scores = eval_data.get("scores", {})
            transcript_lines.append(f"### Turn {i}")
            transcript_lines.append(
                f"- Relevance: {scores.get('relevance')}/10 | "
                f"Specificity: {scores.get('specificity')}/10 | "
                f"Structure: {scores.get('structure')}/10 | "
                f"Confidence: {scores.get('confidence')}/10"
            )
            transcript_lines.append(
                f"- Rating: {eval_data.get('overall_rating')} | "
                f"Observation: {eval_data.get('key_observations', '')}\n"
            )
        transcript_path.write_text("\n".join(transcript_lines), encoding="utf-8")
        console.print(
            f"  [success]✓ Transcript saved to:[/] {transcript_path}"
        )
    else:
        console.print("[warning]  No turns completed — skipping coaching report.[/]")

    console.print()
    console.print("[bold cyan]  Thanks for practicing! Good luck with your interviews! 🚀[/]")
    console.print()


# ── Entry Point ───────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        run_interview()
    except KeyboardInterrupt:
        console.print("\n[warning]Interview cancelled.[/]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[error]Fatal error: {e}[/]")
        sys.exit(1)
