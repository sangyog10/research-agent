# Day 21 — Research → Email Agent (LangGraph, human in the loop)

A LangGraph workflow that researches a topic, drafts an email about it, then
**stops and waits for you** in the browser. You approve it or send it back for
changes. Nothing is emailed without your click.

Everything runs in Streamlit. There is no CLI.

---

## Quick start

```bash
cd day21

uv sync                  # install dependencies into .venv
cp .env.example .env     # then paste your GROQ_API_KEY into .env

uv run streamlit run app.py
```

Opens at <http://localhost:8501>. A free Groq key takes a minute:
<https://console.groq.com/keys>

---

## How it works

```
START → research → extract_facts → draft_email → human_review  ⏸ PAUSES HERE
                                                      │
                      ┌───────────────────────────────┼───────────────────────────────┐
                      │                               │                               │
                 "Approve &                    "Request changes"              "Request changes"
                    send"                        (≤ max revisions)             (limit reached)
                      │                               │                               │
                      ▼                               ▼                               ▼
                    send                           revise                          abort
                      │                               │                               │
                      ▼                               └──→ human_review                ▼
                     END                                                             END
```

The pause is a real LangGraph `interrupt()`, not a UI trick:

```python
# agent/nodes.py
decision = interrupt({...})  # execution stops, invoke() returns
```

```python
# app.py
advance(Command(resume={"approved": True, "feedback": ""}))  # execution continues
```

Three pieces make that survive Streamlit's script reruns:

| Piece | Where | Why |
| --- | --- | --- |
| `MemorySaver` checkpointer | `agent/graph.py` | Stores the paused state |
| `thread_id` | `app.py` → `init_session()` | Names this run inside the checkpointer |
| `st.session_state` | `app.py` | Keeps the graph + thread id alive across reruns |

Each browser session gets its own graph and UUID thread id, so two people using
the app at once never collide.

### What you see

1. **Form** — topic, recipient, how many revisions to allow.
2. **Review** — the draft, with `✅ Approve & send` and `✏️ Request changes`
   (feedback box). Rejecting rewrites the draft and returns you here, up to the
   revision limit; after that it stops without sending.
3. **Result** — delivered / dry run / stopped, plus expanders for the facts,
   sources, your feedback trail and every draft version.

---

## Configuration

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `GROQ_API_KEY` | **yes** | — | Inference |
| `GROQ_MODEL` | no | `openai/gpt-oss-20b` | Any [Groq model](https://console.groq.com/docs/models) |
| `LLM_TEMPERATURE` | no | `0.3` | `0.0` deterministic → `1.0` creative |
| `RESEND_API_KEY` | no | — | Email delivery. **Omit to run in dry-run mode** |
| `EMAIL_FROM` | no | `onboarding@resend.dev` | Sender; must be verified on your Resend domain |

Without `RESEND_API_KEY` the whole workflow runs and only the final network call
is skipped — safe for demos. The sidebar always tells you which mode you're in.

> The default `onboarding@resend.dev` sandbox sender only delivers to the address
> you signed up to Resend with. Verify a domain to send anywhere else.

---

## Files

```
day21/
├── app.py              # the entire UI: form, review buttons, result
├── pyproject.toml      # dependencies (uv), ruff config
├── .env.example        # copy to .env
├── _smoke.py           # end-to-end test, everything stubbed
└── agent/
    ├── config.py       # the only module that reads os.environ
    ├── llm.py          # get_llm() / complete() / lines_from()
    ├── search.py       # DuckDuckGo wrapper
    ├── state.py        # EmailAgentState + initial_state()
    ├── prompts.py      # the three prompt templates
    ├── parsing.py      # "SUBJECT: ... BODY: ..." → (subject, body)
    ├── sender.py       # Resend delivery → SendOutcome
    ├── nodes.py        # research / facts / draft / review / revise / send / abort
    └── graph.py        # StateGraph wiring + checkpointer
```

Two rules keep this maintainable:

- **`agent/` never imports Streamlit.** Nodes return only the keys they change
  and append problems to `state["warnings"]`; `app.py` decides how to show them.
- **One place per concern.** All env access in `config.py`, all model calls in
  `llm.py`, all search in `search.py`, all delivery in `sender.py`.

---

## Testing

```bash
uv run python _smoke.py    # 40 assertions, no network calls
uv run ruff check .
uv run ruff format .
```

`_smoke.py` drives the real app through Streamlit's `AppTest` with the LLM,
search and sender stubbed. It covers both paths: draft → request changes →
approve → sent, and rejecting past the revision limit → abort with nothing sent.
Because the sender is stubbed it cannot send a real email even with a live
`RESEND_API_KEY` in `.env`.

---

## Troubleshooting

**`GROQ_API_KEY is not set`** — `cp .env.example .env`, add the key, restart the
app. Run from the `day21/` directory so `.env` is found.

**`ModuleNotFoundError: agent`** — run `uv run streamlit run app.py` from
`day21/`, not from a parent directory.

**Search returns nothing** — DuckDuckGo rate-limits bursts. The run continues
and the reason appears under "⚠️ Warnings".

**"Dry run" instead of sending** — expected without `RESEND_API_KEY`.

**Resend 403 / "domain is not verified"** — the sandbox sender only reaches your
own Resend signup address. Verify a domain and update `EMAIL_FROM`.

**Changed `.env` but nothing happened** — settings are cached per process;
restart the Streamlit server.
