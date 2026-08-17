# Research → Email Agent

A LangGraph workflow that researches a topic, drafts an email about it, then
**stops and waits for you** in the browser. You approve it or send it back for
changes. Nothing is emailed without your click.

Everything runs in Streamlit. There is no CLI.

---

## Quick start

```bash
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

