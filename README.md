# Research Agent

Two LangGraph agents that share one set of building blocks:

| Agent | Interface | What it demonstrates |
| --- | --- | --- |
| **Email agent** | CLI (`main.py`) | Human-in-the-loop with `interrupt()` / `Command(resume=...)`, checkpointing, revision loops, conditional routing |
| **Research assistant** | Streamlit (`streamlit_app.py`) | Iterative research loop, quality-based routing, live progress via `graph.stream()` |

Both use **Groq** for inference and **DuckDuckGo** for web search.

---

## Quick start

```bash
# 1. Install everything into .venv (uv reads pyproject.toml)
uv sync

# 2. Configure your keys
cp .env.example .env
#    then edit .env and paste your GROQ_API_KEY

# 3a. Run the email agent (terminal)
uv run main.py

# 3b. Run the research assistant (browser)
uv run streamlit run streamlit_app.py
```

A free Groq key takes about a minute: <https://console.groq.com/keys>

---

## Environment variables

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `GROQ_API_KEY` | **yes** | — | Inference for both agents |
| `GROQ_MODEL` | no | `openai/gpt-oss-20b` | Any [Groq model](https://console.groq.com/docs/models) |
| `LLM_TEMPERATURE` | no | `0.3` | `0.0` deterministic → `1.0` creative |
| `RESEND_API_KEY` | no | — | Email delivery. **Omit it to run in dry-run mode** |
| `EMAIL_FROM` | no | `onboarding@resend.dev` | Sender address; must be verified on your Resend domain |

Without `RESEND_API_KEY` the email agent runs the whole workflow and skips only
the final network call, so it is safe to demo.

> The default `onboarding@resend.dev` sandbox sender can only deliver to the
> email address you signed up to Resend with. Verify a domain to send anywhere.

---

## Agent 1 — Research → Email (human in the loop)

```
START → research → extract_facts → draft_email → human_review
                                                      │
                          ┌───────────────────────────┼───────────────────────────┐
                          │                           │                           │
                       approve                reject (≤ max)              reject (> max)
                          │                           │                           │
                          ▼                           ▼                           ▼
                        send                       revise                       abort
                          │                           │                           │
                          ▼                           └──→ human_review           ▼
                         END                                                     END
```

The graph **pauses** at `human_review`. Nothing is sent until you type `y`.
Typing `n` sends your feedback to the revision node and loops back for another
review, up to `--max-revisions` times.

```bash
# Interactive
uv run main.py

# Non-interactive (skip prompts, auto-approve the first draft)
uv run main.py --topic "EU AI Act timeline" --to me@example.com --yes

# Allow more revision rounds
uv run main.py --max-revisions 5

uv run main.py --help
```

Installed as a script too, so `uv run email-agent` works.

### How the pause/resume works

```python
decision = interrupt({...})  # nodes.py — execution stops here
...
app.invoke(Command(resume=decision), config)  # runner.py — execution continues
```

`interrupt()` requires a checkpointer (`MemorySaver`) plus a stable
`thread_id`. Each run gets a fresh UUID thread id, so runs never collide.

---

## Agent 2 — Research assistant (Streamlit)

```
START → input → questions → search → analyze → router
                   ▲                              │
                   └──────── "more research" ─────┘
                                                  │ "good enough"
                                                  ▼
                                                report → END
```

The router stops the loop when **any** of these is true:

- `iteration >= max_iterations` (sidebar slider)
- `quality_score >= quality_threshold` (sidebar slider)
- `len(key_findings) >= max_findings`

`quality_score` is `min(0.2 × unique_findings, 1.0)`.

```bash
uv run streamlit run streamlit_app.py     # → http://localhost:8501
```

---

## Project structure

```
day21/
├── main.py                    # CLI entry point  → langgraph_capstone.cli:main
├── streamlit_app.py           # Streamlit entry  → langgraph_capstone.ui:main
├── pyproject.toml             # deps + scripts + ruff config (uv reads this)
├── .env.example               # copy to .env
└── src/langgraph_capstone/
    ├── config.py              # every env var lives here (Settings)
    ├── llm.py                 # get_llm() / complete() / lines_from()
    ├── search.py              # DuckDuckGo wrapper, shared by both agents
    ├── console.py             # terminal formatting helpers
    ├── cli.py                 # interactive review loop for agent 1
    ├── ui.py                  # Streamlit interface for agent 2
    ├── email_agent/
    │   ├── state.py           # EmailAgentState + initial_state()
    │   ├── prompts.py         # prompt templates
    │   ├── parsing.py         # "SUBJECT: ... BODY: ..." → (subject, body)
    │   ├── sender.py          # Resend delivery, returns SendOutcome
    │   ├── nodes.py           # research / facts / draft / review / revise / send / abort
    │   ├── graph.py           # StateGraph wiring + checkpointer
    │   └── runner.py          # start / resume / is_waiting_for_human
    └── research_agent/
        ├── state.py           # ResearchState + initial_state()
        ├── prompts.py         # prompt templates
        ├── nodes.py           # input / questions / search / analyze / report
        └── graph.py           # StateGraph wiring + progress weights
```

Design rules used throughout:

- **Nodes return only the keys they change** and never mutate state in place.
- **Nodes never import UI code.** The research agent collects problems in
  `state["errors"]`; the UI decides how to show them.
- **One place per concern:** all env access in `config.py`, all model creation
  in `llm.py`, all search in `search.py`, all email delivery in `sender.py`.

---

## Bugs fixed from the original scripts

`research.py`:

| Issue | Fix |
| --- | --- |
| `IndentationError` in the send block — the file could not even be imported | Rewritten as `email_agent/sender.py` |
| `to`, `subject`, `body` were undefined inside `resend.Emails.send()` | Values passed in explicitly |
| `resend.api_key` was never assigned, so every send would fail with 401 | Set from `Settings` before sending |
| `line[len("SUBJECT:")].strip()` indexed a **single character** instead of slicing, so every subject was one letter | Regex-based parser in `parsing.py`, tolerant of `**Subject:**` |
| `EMAIL_FROM` read but never used; sender hard-coded | Uses `settings.email_from` |
| Rejecting past `max_revisions` routed to `send`, which then refused — reported as an error | Explicit `abort` node ending the graph cleanly |
| `thread_id` hard-coded to `"email-demo-001"` — two runs shared a checkpoint | UUID per run in `runner.new_config()` |
| Missing `GROQ_API_KEY` failed deep inside a node | Checked up front with setup instructions |
| Unused `smtplib` / `EmailMessage` imports | Removed |
| `.env` never loaded | `load_dotenv()` in `config.py` |

`streamlit.py`:

| Issue | Fix |
| --- | --- |
| `import day21.streamlit as st` — the app crashed on line 7 | `import streamlit as st` |
| File named `streamlit.py`, shadowing the real package | Renamed to `streamlit_app.py` |
| Progress bar was **fake**: it looped the 5 node names with `time.sleep(0.5)` and marked them all done *before* `invoke()` ran | Real progress from `graph.stream(stream_mode="updates")` |
| `quality_threshold` slider was collected but never used (`0.8` hard-coded in the router) | Threshold stored in state and read by the router |
| "Load Example" button + `st.selectbox` inside it — the box vanished on rerun | Plain selectbox bound to `session_state` |
| `col1, col2, col3 = st.columns(3)` shadowed the outer `col1` while inside `with col1:` | Renamed to `left/middle/right` |
| Nodes called `st.error()`, coupling graph logic to the UI | Errors accumulate in `state["errors"]` |
| `analyzer_node` early-return dropped `status`/`current_node` keys | All branches return a consistent shape |
| `search_results` mutated in place from state | Copied before extending |
| Duplicate findings inflated `quality_score` | Case-insensitive dedupe |
| Different provider from `research.py` (`ChatOpenAI` + custom `base_url`) | Both agents now use Groq via `llm.get_llm()` |
| Unused `json` import, unused `current_node` state key | Removed |

---

## Development

```bash
uv run ruff check .        # lint
uv run ruff format .       # format
uv add <package>           # add a dependency (updates pyproject + uv.lock)
```

---

## Troubleshooting

**`GROQ_API_KEY is not set`** — run `cp .env.example .env` and paste your key.
Commands must run from the `day21/` directory so `.env` is discovered.

**`ModuleNotFoundError: langgraph_capstone`** — use `uv run ...`, not bare
`python`. `uv run` installs the project into `.venv` first.

**Search returns nothing / rate limited** — DuckDuckGo throttles bursts. Wait a
few seconds; the run continues with a warning instead of crashing.

**Email says "dry run"** — expected without `RESEND_API_KEY`. Add one to send.

**Resend 403 / "domain is not verified"** — the sandbox sender only delivers to
your own Resend signup address. Verify a domain and update `EMAIL_FROM`.
