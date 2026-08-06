
# AI Mock Interview Coach

A multi-agent CLI system that conducts realistic mock interviews, evaluates candidate responses in real-time with structured scoring, and delivers personalized coaching feedback — powered by Groq (LLaMA 3.3 70B).

---

## Architecture Overview

### Why Three Agents — and Why They're Genuinely Different

This system is **not** three sequential LLM calls dressed up as "agents." Each agent has a fundamentally different **role**, **persona**, **output contract**, **decision authority**, and **behavioral constraints**. They are designed to be adversarial-cooperative: the Evaluator silently judges without the candidate knowing, the Interviewer follows orders without seeing scores, and the Coach synthesizes what neither could alone.

| Dimension | Interviewer Agent | Evaluator Agent | Coach Agent |
|---|---|---|---|
| **Role** | Conversational partner — asks questions, listens | Silent judge — scores and routes | Post-game analyst — synthesizes and advises |
| **When it runs** | Every turn (before candidate speaks) | Every turn (after candidate speaks) | Once (after interview ends) |
| **Output format** | Free-form plain text (natural speech) | Strict JSON object (machine-parseable) | Structured Markdown report |
| **Persona** | Role-specific (e.g., "Senior Engineering Manager", "VP Product") — stays in character | No persona — objective analytical engine | Supportive career coach |
| **Sees candidate?** | Yes — directly addresses them | No — never speaks to candidate | Yes — addresses them in final report |
| **Gives feedback?** | **Never** — strictly prohibited from hinting or evaluating | Only to the Interviewer (via `interviewer_direction`) | Only to the candidate (final report) |
| **Temperature** | 0.75 (creative, natural conversation) | 0.3 (deterministic, consistent scoring) | 0.6 (balanced synthesis) |
| **Decision authority** | Chooses *how* to phrase a question | Decides *what happens next* (follow-up vs. move on) | Decides the *final verdict* (Strong Hire / Tricky Select / Not Good Hire) |
| **Context window** | Full conversation history + remaining concepts | Single turn only (question + answer + concept list) | Entire transcript + all evaluation scores |
| **Token budget** | 512 max (concise questions) | 512 max (compact JSON) | 3000 max (detailed report) |

### The Key Insight: Separation of Concerns

The **Interviewer never sees the scores**. It only receives a plain-English `interviewer_direction` string from the Evaluator (e.g., *"Candidate was vague about tiling — probe deeper on memory hierarchy"*). This prevents the Interviewer from breaking character by saying things like *"Your score was 3/10, let's try again."*

The **Evaluator never speaks to the candidate**. It operates as a silent, stateless scoring engine — it receives one (question, answer) pair, scores it on 4 dimensions, and outputs routing instructions. It has no memory of previous turns.

The **Coach only activates once** at the end. It receives the *entire* transcript and *all* evaluator scores — information that neither the Interviewer nor the Evaluator ever had access to in full. This allows it to spot patterns across turns (e.g., *"You consistently scored low on Specificity"*) that no single-turn agent could detect.

---

### Orchestration: The State Machine

The orchestrator (`orchestrator.py`) is **pure Python logic with zero LLM calls**. It manages a central `InterviewState` dataclass and implements deterministic routing — the LLM agents never decide control flow.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INTERVIEW LOOP                               │
│                                                                     │
│   Interviewer ──Ask Question──► User ──Answer──► Evaluator          │
│                                                       │             │
│                                             Update State & Scores   │
│                                                       │             │
│                                           ┌───────────┼──────────┐  │
│                                           │    Conditional Router │  │
│                                           │    (Python, not LLM)  │  │
│                                           └───┬───────┬──────┬───┘  │
│                                               │       │      │      │
│                                          weak/vague  strong  turn≥7 │
│                                          Follow-up   Next    or     │
│                                               │      Topic  concepts│
│                                               │       │    exhausted│
│                                               ▼       ▼      │      │
│                                           Interviewer ◄───────┘      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                                       │
                                                       ▼
                                                    Coach
                                              (Final Report)
```

#### Routing Rules (Deterministic — No LLM Involved)

| Condition | Action | Why |
|---|---|---|
| `overall_rating == "strong"` | Move concept → covered, pick **random** next topic | Candidate demonstrated mastery — no need to linger |
| `overall_rating == "weak"` or `"partial"` | Stay on **same concept**, Interviewer follows up | Give candidate another chance to demonstrate understanding |
| Consecutive follow-ups ≥ 2 on same topic | **Force move** to next topic anyway | Prevents the interview from getting stuck on one concept |
| `current_turn >= 7` | Exit loop → Coach | Hard turn limit reached |
| `remaining_concepts == []` | Exit loop → Coach | All concepts covered |

#### What the Orchestrator Tracks (InterviewState)

```python
@dataclass
class InterviewState:
    target_role_canonical: str        # "AI_ML_Engineer"
    remaining_concepts: list[dict]    # Concepts not yet covered (shrinks each turn)
    covered_concepts: list[dict]      # Successfully covered (grows each turn)
    current_concept: dict             # Active concept being probed this turn
    transcript: list[dict]            # Full conversation history
    evaluations: list[dict]          # All evaluator JSON outputs
    current_turn: int                # 0-indexed turn counter
    max_turns: int = 7               # Hard stop
```

---

### Agent Deep Dives

#### Agent 1: The Interviewer (Persona & Dialogue Engine)

**File:** `agents/interviewer.py` | **Prompt:** `prompts/interviewer_prompt.txt`

The Interviewer is a **conversational actor**. It maintains a consistent persona (e.g., *"a Principal ML Scientist at a leading AI research lab"*) and its core behavioral constraint is that it **must never evaluate, hint, or give feedback**. It receives its marching orders from the Evaluator's `interviewer_direction` field but never sees the numerical scores.

**What makes it genuinely different:**
- Maintains **full conversation history** in its context window for natural dialogue flow
- **Adapts difficulty dynamically** based on a rolling average of recent scores (without seeing the scores directly — difficulty is pre-computed by the orchestrator)
- Has a **consecutive follow-up limiter** — after 1 follow-up on the same weak topic, it's forced to move on, ensuring diverse coverage
- Randomly selects concepts from the remaining pool (not sequential), simulating a real interviewer who jumps between topics

**Behavioral constraints (from prompt):**
> - Stay in character at ALL times. Never say "as an AI".
> - NEVER give feedback, hints, or evaluate the candidate's answer.
> - Ask exactly ONE question per turn.
> - Do NOT get stuck on the same topic for more than 2 consecutive turns.
> - Pick questions RANDOMLY from remaining concepts.

---

#### Agent 2: The Evaluator (Structured JSON Scoring Engine)

**File:** `agents/evaluator.py` | **Prompt:** `prompts/evaluator_prompt.txt`

The Evaluator is a **stateless analytical engine**. It receives exactly one (question, answer) pair per turn and outputs a strict JSON object. It has **no persona**, **no conversation history**, and **never speaks to the candidate**. Its output directly controls the Interviewer's next action via the `interviewer_direction` field.

**What makes it genuinely different:**
- Operates in **JSON mode** (`response_format: json_object`) — completely different output contract from the other agents
- Is the **only agent with decision authority** over what happens next (follow-up vs. new topic)
- Has a **detailed scoring rubric** with anchor descriptions for each score (1-10) across 4 dimensions
- Includes **edge case detection logic** in its prompt — explicit instructions for handling "I don't know", off-topic tangents, and partial answers
- Has a **5-layer fallback parser** in code to handle malformed JSON (strip code fences → extract embedded JSON → clamp out-of-range scores → validate rating → complete fallback)

**Output contract (strictly enforced):**
```json
{
  "scores": {
    "relevance": 8,
    "specificity": 7,
    "structure": 8,
    "confidence": 7
  },
  "overall_rating": "strong",
  "concepts_covered": ["Flash Attention"],
  "interviewer_direction": "Strong response. Move to the next concept.",
  "key_observations": "Candidate demonstrated deep understanding of memory hierarchy."
}
```

**Scoring dimensions:**
| Dimension | What it measures |
|---|---|
| **Relevance** (1-10) | Does the answer address the actual question asked? |
| **Specificity** (1-10) | Are there concrete details, examples, and technical depth? |
| **Structure** (1-10) | Is the answer well-organized with logical flow? |
| **Confidence** (1-10) | Does the candidate sound assured and authoritative? |

---

#### Agent 3: The Coach (Post-Interview Synthesis Engine)

**File:** `agents/coach.py` | **Prompt:** `prompts/coach_prompt.txt`

The Coach is a **synthesis engine** that only runs once, after the interview ends. It receives the **complete transcript** and **all evaluator scores** — information that neither the Interviewer nor the Evaluator ever had access to holistically. This allows it to identify cross-turn patterns and deliver a comprehensive report.

**What makes it genuinely different:**
- Has **the largest context window** (entire transcript + all scores) — neither other agent sees this
- Is the **only agent that speaks directly to the candidate** with evaluative feedback
- Outputs **structured Markdown** (not JSON, not plain text) — a third distinct output format
- **Cites specific transcript moments** with turn numbers and quotes — grounded in evidence
- Is the **only agent that assigns the final verdict**: Strong Hire / Tricky Select / Not Good Hire

**Final classification labels:**
| Verdict | Criteria | Avg Score |
|---|---|---|
| **Strong Hire** | Consistently strong answers, deep expertise, excellent communication | 7+ |
| **Tricky Select** | Borderline — some solid answers but noticeable gaps, could go either way | 4–6 |
| **Not Good Hire** | Fundamental gaps in knowledge or communication, struggled with most questions | Below 4 |

---

### Knowledge Pipeline

#### Role Resolution (Zero-Embedding)

Instead of using vector embeddings to match free-text role inputs, we use a lightweight **alias dictionary** with substring fallback:

```python
ROLE_ALIASES = {
    "ml engineer": "AI_ML_Engineer",
    "machine learning": "AI_ML_Engineer",
    "backend dev": "Backend_Engineer",
    "data analyst": "Data_Analyst",
    "pm": "Product_Manager",
    ...
}
```

If no alias matches → falls back to `General_Interview_Mode` with universal engineering concepts.

#### Concept Triplets (from `roles1.json`)

Each role has concepts organized by focus area (**technical**, **behavioral**, **case**, **mixed**):

```json
["Flash Attention", "accelerate_self-attention_computation_by", "Tiled Matrix Multiplication"]
```

Concepts are **randomly shuffled** at startup so every interview session feels different. The orchestrator tracks which concepts are covered vs. remaining to prevent repetition and ensure breadth.

---

## Project Structure

```
interview_coach/
├── main.py                    # CLI entry point + Rich-formatted UI
├── orchestrator.py            # State machine (pure Python, no LLM calls)
├── agents/
│   ├── interviewer.py         # Persona-consistent question generation
│   ├── evaluator.py           # JSON scoring engine with fallback parsing
│   └── coach.py               # Markdown report synthesis
├── knowledge/
│   ├── role_resolver.py       # Alias dictionary + fallback logic
│   └── loader.py              # In-memory triplet storage from roles1.json
├── prompts/
│   ├── interviewer_prompt.txt # Persona rules, difficulty calibration
│   ├── evaluator_prompt.txt   # Scoring rubric, edge case handling, JSON format
│   └── coach_prompt.txt       # Report structure, citation rules
├── roles1.json                # 6 roles × 4 focus areas × 10-24 concepts each
├── .env                       # GROQ_API_KEY, model config
├── requirements.txt           # groq, rich, pydantic, python-dotenv
└── Dockerfile                 # One-command containerized execution
```

---

## Setup & Run Instructions

### Prerequisites
- Python 3.10+
- A Groq API Key ([console.groq.com](https://console.groq.com))

### Local Setup
1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd interview_coach
   ```
2. **Create a `.env` file:**
   ```env
   GROQ_API_KEY=your_api_key_here
   GROQ_MODEL=llama-3.3-70b-versatile
   MAX_TURNS=7
   ```
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Run the application:**
   ```bash
   python main.py
   ```

### Docker Setup
1. **Build the image:**
   ```bash
   docker build -t interview-coach .
   ```
2. **Run the container:**
   ```bash
   docker run -it --env-file .env interview-coach
   ```

---

## Key Design Decisions & Trade-offs

| Decision | What we chose | Alternative considered | Why |
|---|---|---|---|
| **Role resolution** | Alias dictionary + substring match | Vector embeddings (sentence-transformers) | Zero cold-start, no embedding model needed, O(1) lookup |
| **Concept storage** | In-memory dict from `roles1.json` | External vector DB (Pinecone/Chroma) | No infra dependency, sub-ms retrieval, sufficient for ~200 concepts |
| **Orchestration** | Deterministic Python state machine | LLM-driven flow control | Predictable, no infinite loops, testable routing logic |
| **Evaluator output** | Strict JSON mode | Free-text with regex parsing | Reliable structured data, enables deterministic routing |
| **Context budgeting** | Inject only `remaining_concepts` | Full concept list every turn | Prevents token bloat, stops repetitive questions, reduces latency |
| **Follow-up limit** | Max 1 follow-up per concept | Unlimited follow-ups on weak topics | Ensures breadth of coverage across the 7-turn budget |
| **Concept selection** | Random shuffle at startup | Sequential from JSON order | Each session feels different; simulates real interview unpredictability |
| **Turn limit** | Hard cap at 7 | LLM decides when to stop | Predictable session length, prevents runaway API costs |

---

## Example Interview Transcripts

### Transcript 1: Strong Candidate (ML Engineer, Technical)

**Intake:**
- **Role:** ML Engineer → resolved to `AI_ML_Engineer` ✓
- **Focus:** Technical
- **Background:** "2 years building LLM-powered applications, familiar with transformers and fine-tuning"

**Turn 1**
- **Interviewer:** Welcome! I'm the hiring manager for our Applied ML team. Let's jump right in — can you walk me through how Flash Attention optimizes standard scaled dot-product attention, particularly regarding memory access patterns?
- **Candidate:** Standard attention materializes the full O(N²) attention matrix to HBM, which is the major bottleneck for long sequences. Flash Attention uses tiling to compute exact attention in SRAM by breaking Q, K, V into blocks, computing partial softmax in each tile, then combining results — never writing the NxN intermediate matrix to HBM. This reduces memory IO from O(N²) to O(N), making it both faster and more memory-efficient.
- **Evaluator JSON:**
  ```json
  {
    "scores": { "relevance": 9, "specificity": 9, "structure": 8, "confidence": 9 },
    "overall_rating": "strong",
    "concepts_covered": ["Flash Attention"],
    "interviewer_direction": "Strong response on Flash Attention. Move to the next concept.",
    "key_observations": "Excellent — correctly identified O(N²) HBM bottleneck, tiling in SRAM, and memory IO reduction."
  }
  ```
  *Routing: strong → move to next random concept*

**Turn 2**
- **Interviewer:** Great. Now, when adapting large pre-trained models for specific tasks, LoRA has become very popular. Can you break down how it works and what makes it memory-efficient?
- **Candidate:** LoRA freezes all pre-trained weights and injects small trainable rank-decomposition matrices into transformer layers. Instead of updating the full weight matrix W (d×d), you update W + BA where B is d×r and A is r×d, with r being much smaller than d — typically 4-16. This reduces trainable parameters by 10,000x while maintaining comparable performance. It's memory-efficient because gradients only flow through the small BA matrices.
- **Evaluator JSON:**
  ```json
  {
    "scores": { "relevance": 9, "specificity": 9, "structure": 9, "confidence": 8 },
    "overall_rating": "strong",
    "concepts_covered": ["Low-Rank Adaptation"],
    "interviewer_direction": "Strong response. Move to the next concept.",
    "key_observations": "Textbook explanation with exact matrix dimensions and typical rank values."
  }
  ```
  *Routing: strong → move to next random concept*

**Turn 3**
- **Interviewer:** Shifting gears — how would you design a RAG pipeline, and what are the key failure modes?
- **Candidate:** I'd chunk documents semantically, embed them with a model like BGE or E5, store in a vector DB. At query time, embed the query, retrieve top-K via approximate nearest neighbors, then re-rank with a cross-encoder before injecting into the LLM prompt. Key failure modes: poor chunking loses context boundaries, embedding model domain mismatch, "lost in the middle" where LLMs ignore central retrieved passages, and stale indexes when source data updates.
- **Evaluator JSON:**
  ```json
  {
    "scores": { "relevance": 9, "specificity": 8, "structure": 9, "confidence": 8 },
    "overall_rating": "strong",
    "concepts_covered": ["RAG Pipeline"],
    "interviewer_direction": "Comprehensive answer. Move to next concept.",
    "key_observations": "Strong end-to-end design with practical failure mode analysis."
  }
  ```

*(Interview continues through 7 turns with consistently high scores)*

**Coach Report (Final Verdict: Strong Hire):**
> **Overall:** Exceptional performance. You demonstrated deep, practical knowledge of modern ML engineering across attention mechanisms, parameter-efficient fine-tuning, and production RAG pipelines.
>
> **Strengths:** In Turn 1, your Flash Attention explanation was precise — "tiling to compute exact attention in SRAM, reducing memory IO from O(N²) to O(N)." In Turn 2, you gave exact rank dimensions (r=4-16) for LoRA, showing hands-on experience.
>
> **Verdict: Strong Hire** — consistently scored 8-9 across all dimensions with expert-level specificity.

---

### Transcript 2: Weak Candidate (Backend Engineer, Technical)

**Intake:**
- **Role:** Backend Engineer → resolved to `Backend_Engineer` ✓
- **Focus:** Technical
- **Background:** "CS graduate, some web development experience"

**Turn 1**
- **Interviewer:** Hi, I'm the tech lead on our platform team. Let's start — can you explain why connection pooling matters for a high-traffic backend service?
- **Candidate:** Connection pooling is good because it keeps connections in a pool so the database doesn't crash. It makes things faster.
- **Evaluator JSON:**
  ```json
  {
    "scores": { "relevance": 4, "specificity": 2, "structure": 3, "confidence": 3 },
    "overall_rating": "weak",
    "concepts_covered": [],
    "interviewer_direction": "Candidate was vague. Probe deeper: ask specifically about what makes opening a new connection expensive (TCP handshake, TLS negotiation, memory allocation).",
    "key_observations": "Buzzword-level answer. Missed the core cost model of per-connection overhead."
  }
  ```
  *Routing: weak → follow up on same concept*

**Turn 2**
- **Interviewer:** Could you elaborate on what exactly makes opening a new database connection expensive? What's happening at the network level?
- **Candidate:** I think it's because the database has to authenticate you each time, which takes a while.
- **Evaluator JSON:**
  ```json
  {
    "scores": { "relevance": 3, "specificity": 2, "structure": 4, "confidence": 2 },
    "overall_rating": "weak",
    "concepts_covered": [],
    "interviewer_direction": "Still struggling. Already followed up once — move to a fresh topic to maintain interview diversity.",
    "key_observations": "Incorrect focus. Auth is minor; primary costs are TCP 3-way handshake, TLS negotiation, and server-side memory allocation."
  }
  ```
  *Routing: weak but consecutive follow-up limit reached → force move to new topic*

**Turn 3**
- **Interviewer:** Let's switch topics. Can you explain the Circuit Breaker pattern and when you'd use it in a microservices architecture?
- **Candidate:** The circuit breaker is when you break the microservice into smaller parts so if one breaks the rest are fine.
- **Evaluator JSON:**
  ```json
  {
    "scores": { "relevance": 2, "specificity": 1, "structure": 3, "confidence": 3 },
    "overall_rating": "weak",
    "concepts_covered": [],
    "interviewer_direction": "Fundamental misunderstanding. Candidate confused circuit breaker pattern with microservice decomposition. Follow up with a simpler framing.",
    "key_observations": "Confused the Circuit Breaker pattern (fail-fast to prevent cascading failures) with general service decomposition."
  }
  ```

**Turn 4**
- **Interviewer:** The Circuit Breaker is actually about stopping calls to a failing downstream service to prevent cascade failures. Moving on — what caching strategies have you used to reduce database load?
- **Candidate:** I don't know much about caching strategies, sorry.
- **Evaluator JSON:**
  ```json
  {
    "scores": { "relevance": 1, "specificity": 1, "structure": 3, "confidence": 2 },
    "overall_rating": "weak",
    "concepts_covered": [],
    "interviewer_direction": "Candidate admitted unfamiliarity. Move to next concept.",
    "key_observations": "Explicit 'I don't know' — handled as specified in edge case rules."
  }
  ```

*(Interview continues through 7 turns with consistently low scores)*

**Coach Report (Final Verdict: Not Good Hire):**
> **Overall:** The interview revealed significant gaps in foundational backend engineering concepts.
>
> **Areas for Improvement:** In Turn 1, you described connection pooling as "it makes things faster" — a strong answer would explain TCP handshake costs (~1.5 RTT), TLS negotiation overhead, and server-side memory allocation per connection. In Turn 3, you confused the Circuit Breaker pattern with microservice decomposition — these are fundamentally different concepts.
>
> **Verdict: Not Good Hire** — averaged 2.2 across all dimensions. Needs significant foundational study before re-attempting.

---

### Transcript 3: Tricky/Edge Case (Unrecognized Role → Fallback + Off-topic + Partial)

**Intake:**
- **Role:** Blockchain Developer → **not recognized** → falls back to `General_Interview_Mode` ⚠️
- **Focus:** Technical
- **Background:** "Worked on Solana smart contracts for 1 year"

**Turn 1**
- **Interviewer:** Welcome. I see you have a background in blockchain — we'll be covering general software engineering fundamentals today. Let's start: can you explain the difference between optimistic and pessimistic locking?
- **Candidate:** Optimistic locking is when you just hope things work out, and pessimistic is when you assume it'll fail so you lock everything. By the way, this reminds me of how Solana handles account locking — they use optimistic concurrency for parallel transaction processing.
- **Evaluator JSON:**
  ```json
  {
    "scores": { "relevance": 3, "specificity": 2, "structure": 4, "confidence": 5 },
    "overall_rating": "weak",
    "concepts_covered": [],
    "interviewer_direction": "Candidate went off-topic to Solana. The definitions were oversimplified. Gently redirect: ask specifically about what happens when two transactions conflict under optimistic locking.",
    "key_observations": "Incorrect definitions ('hope' vs 'assume fail') and off-topic tangent to Solana."
  }
  ```
  *Routing: weak → follow up*

**Turn 2**
- **Interviewer:** Let's stay focused on databases. With optimistic locking, what specifically happens when two transactions try to update the same row at the same time?
- **Candidate:** The first transaction to commit succeeds. The second one detects that the version number changed since it started, so it gets a conflict error. The application then has to decide whether to retry or abort — usually you retry with exponential backoff.
- **Evaluator JSON:**
  ```json
  {
    "scores": { "relevance": 8, "specificity": 7, "structure": 7, "confidence": 7 },
    "overall_rating": "strong",
    "concepts_covered": ["Problem Decomposition"],
    "interviewer_direction": "Good recovery. Candidate correctly explained version-based conflict detection. Move to next concept.",
    "key_observations": "Solid answer — version checking, conflict detection, and retry with backoff."
  }
  ```
  *Routing: strong → move to next random concept*

**Turn 3**
- **Interviewer:** Nice recovery. Now, how would you design an API rate limiter for a service handling thousands of requests per second?
- **Candidate:** I'd use a counter per user in Redis with a TTL matching the rate window. On each request, increment the counter — if it exceeds the limit, return 429. For distributed systems, you'd need a sliding window approach rather than fixed windows to avoid burst issues at window boundaries.
- **Evaluator JSON:**
  ```json
  {
    "scores": { "relevance": 7, "specificity": 5, "structure": 6, "confidence": 6 },
    "overall_rating": "partial",
    "concepts_covered": [],
    "interviewer_direction": "Candidate mentioned Redis and sliding windows but was vague on the sliding window implementation. Probe: ask how the sliding window algorithm actually works.",
    "key_observations": "Good direction but lacked specificity on sliding window mechanics (e.g., sorted set with timestamps vs. hybrid fixed/sliding)."
  }
  ```
  *Routing: partial → follow up on same concept*

**Turn 4**
- **Interviewer:** You mentioned sliding windows — can you walk me through how a sliding window rate limiter actually works under the hood?
- **Candidate:** You keep a sorted set in Redis where each entry is a timestamp of a request. On each new request, you remove all entries older than the window size, count what's left, and compare against the limit. If under limit, add the new timestamp and allow. The downside is memory — each request stores an entry, so for high-traffic APIs you might prefer a token bucket instead.
- **Evaluator JSON:**
  ```json
  {
    "scores": { "relevance": 8, "specificity": 7, "structure": 8, "confidence": 7 },
    "overall_rating": "strong",
    "concepts_covered": ["Trade-off Analysis"],
    "interviewer_direction": "Strong follow-up. Candidate explained sorted set mechanics and even noted the memory trade-off with token bucket alternative. Move on.",
    "key_observations": "Good — explained sorted set approach, cleanup logic, and proactively compared with token bucket."
  }
  ```

*(Interview continues with mixed results through 7 turns)*

**Coach Report (Final Verdict: Tricky Select):**
> **Overall:** Mixed performance with a notable pattern: you struggled initially on several topics but recovered well when given focused follow-up questions.
>
> **Strengths:** In Turn 2, you recovered impressively on optimistic locking — "The second one detects that the version number changed since it started, so it gets a conflict error." In Turn 4, you proactively compared sliding window vs. token bucket trade-offs.
>
> **Areas for Improvement:** In Turn 1, you went off-topic to discuss Solana when asked about database locking. In a real interview, answer the specific question first before drawing parallels. Your initial definitions of optimistic/pessimistic locking were oversimplified.
>
> **Verdict: Tricky Select** — average scores around 5.5. You clearly have technical intuition and can reason well when prompted, but initial answers tend to be shallow or off-topic. With focused preparation on giving structured first responses, you'd be a much stronger candidate.
