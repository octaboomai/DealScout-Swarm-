# DealScout Swarm™

> A white-label AI service that leverages swarm intelligence to empower businesses with autonomous deal-scouting agents. Inspired by collective decision-making in nature, these agents collaborate in real time to identify opportunities, analyze markets, and deliver actionable insights without centralized control.

## What it does

DealScout Swarm is a Streamlit-based B2B market intelligence platform. You ask a business question (e.g., "Give me a deep dive on Ola Electric vs Ather Energy"), and a multi-agent swarm goes to work:

- **Engagement Manager** — analyzes your request and routes it
- **Market Analyst** — gathers live web and financial data using DuckDuckGo search
- **Strategy Associate** — drafts a structured intelligence memo
- **Risk Director** — audits claims and flags risks
- **Managing Partner** — structures the final JSON payload with metrics, risk matrix, and recommendations

The output is rendered as a premium dark-themed dashboard with key metrics, trend indicators, and a risk matrix.

## Features

- **Multi-agent swarm engine** — 5 specialized AI agents collaborate on each query
- **Live web search** — real-time market data via DuckDuckGo
- **PDF document context** — upload business documents for context-aware analysis
- **Structured JSON output** — metrics, risk matrix, recommendations — not just text
- **Premium dark UI** — custom-styled Streamlit dashboard with Inter font
- **Supabase auth** — real per-user accounts with free and Pro tiers
- **Token-based billing** — Pro users get token packs via WhatsApp + UPI

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit (custom CSS, dark theme) |
| AI engine | OpenAI API (multi-agent orchestration) |
| Web search | DuckDuckGo (ddgs) |
| Auth & DB | Supabase |
| PDF parsing | PyPDF2 |
| Email | Resend |

## Quick start

```bash
git clone https://github.com/octaboomai/DealScout-Swarm-.git
cd DealScout-Swarm-
pip install -r requirements.txt
streamlit run app.py
```

Then open `http://localhost:8501` in your browser.

## Configuration

Set these environment variables before running:

```bash
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
RESEND_API_KEY=re_...
```

## Project structure

```
DealScout-Swarm-/
├── app.py              # Streamlit UI + dashboard rendering
├── swarm_engine.py     # Multi-agent swarm orchestration
├── auth.py             # Supabase auth, tiers, token management
├── requirements.txt    # Python dependencies
└── · GITIGNORE
```

## Tiers

- **Free** — limited prompts and PDF uploads per time window
- **Pro** — token-based, top up via WhatsApp + UPI

## License

MIT — see [LICENSE](LICENSE).

## Maintained by

[@octaboomai](https://github.com/octaboomai)