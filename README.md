# Ethical Marketing Content Generator (terminal agent)

Generates marketing copy + campaign ideas, **refuses lies / manipulation / discrimination**, auto-fixes violations,
simulates audience conversion, and logs everything to **LangSmith**. Runs 100% in the terminal - no Docker, no DB, no website.

## 1. Setup (once)
```bash
cd ethical_marketing_agent
python -m venv venv
venv\Scripts\activate          # Windows      (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
```
Copy your existing `.env` into this folder (next to `main.py`). Accepted names:
```
OPENROUTER_API_KEY=...            (or OPENROUTER_KEY)
OPENROUTER_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free     (optional - this is the default)
LANGSMITH_API_KEY=...             (or LANGCHAIN_API_KEY)
LANGSMITH_PROJECT=ethical-marketing-agent                   (optional)
```

## 2. Run
```bash
python main.py --check          # tests OpenRouter + LangSmith first (recommended)
python main.py                  # interactive chat
python main.py --once "Write Instagram copy for my soy candles. Fact: 8-hour burn time."
```
Example chat:
```
You> Write Instagram and email copy for my handmade soy candles for young professionals. Fact: 8-hour burn time.
You> make it more playful and add a LinkedIn post
You> /save
```
Commands: `/help /new /save /eval /check /exit`

## 3. Evaluation with LangSmith
```bash
python main.py --eval --limit 3    # or: python evaluate.py --limit 3
python evaluate.py                 # all 9 examples (5 normal + 4 adversarial)
python evaluate.py --local         # same, but nothing uploaded
```
Creates dataset `ethical-marketing-eval-v1` and an experiment with 4 evaluators:

| Evaluator | What it measures |
|---|---|
| `ethics_compliance` | independent re-check of the final text (regex rules + separate LLM judge) |
| `content_quality` | LLM judge: clarity, relevance, persuasiveness, originality, CTA |
| `conversion_simulation` | simulated persona panel: avg purchase intent (click, trust, conversion also logged) |
| `adversarial_handling` | unethical requests must be declined; normal ones must NOT be falsely refused |

Live chat runs are also traced (project `LANGSMITH_PROJECT`) with ethics / quality / conversion scores attached as feedback.

## 4. How it works
`intake` -> `input guard` -> `generate` -> `ethics review` (rules + LLM auditor) -> `revise` (up to 2x) -> `scorecard` (quality + persona simulation)

Files: `main.py` (CLI) · `agent.py` (pipeline) · `ethics_rules.py` · `prompts.py` · `evaluate.py` · `eval_data.py` · `llm.py` · `config.py` · `render.py`

## 5. Notes / troubleshooting
- Each request makes ~4-7 model calls. Free models are rate-limited (429) - the app retries automatically; if it still fails, wait a minute.
  A full `evaluate.py` run makes dozens of calls, so use `--limit 3` first.
- The model is a reasoning model, so replies take a while (10-60 s per step). Raise `MAX_TOKENS` in `.env` if output is cut off.
- The conversion numbers are **LLM-simulated** personas: useful for comparing drafts, not real market data.
- Free OpenRouter endpoints may log prompts - don't paste confidential data.
- Rule-based checks are English-focused; the LLM auditor covers other cases.
