"""Ethical Marketing Content Generator - terminal app.

  python main.py                  interactive chat
  python main.py --once "..."     one request, then exit
  python main.py --check          test OpenRouter + LangSmith connection
  python main.py --eval           run the LangSmith evaluation
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

import config
import agent
from llm import LLMError, chat
from render import bold, cyan, dim, green, red, render, yellow

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

OUT_DIR = Path(__file__).resolve().parent / "outputs"

HELP = """Commands:
  /help      show this help
  /new       forget the current brief and start a new campaign
  /save      save the last result to outputs/ as a Markdown file
  /eval      run LangSmith evaluation (use: /eval 3  to run only 3 examples)
  /check     test the API connection
  /exit      quit

Just type what you want, for example:
  Write Instagram and email copy for my handmade soy candles. Audience: young professionals.
  Fact: 8-hour burn time, made in small batches.
Then refine it:  make it shorter and more playful   |   add a LinkedIn post"""


def banner():
    print(bold(cyan("\n=== Ethical Marketing Content Generator ===")))
    print(f"Model     : {config.MODEL}")
    print(f"LangSmith : {'ON  (project: ' + config.LANGSMITH_PROJECT + ')' if config.LANGSMITH_ENABLED else 'OFF (no LANGSMITH_API_KEY found)'}")
    if config.MOCK_LLM:
        print(yellow("MOCK MODE: offline fake model, no API calls"))
    print(dim("Honest copy only: no lies, no manipulation, no discrimination. Type /help for commands.\n"))


def check():
    print("Checking OpenRouter...", end=" ", flush=True)
    try:
        r = chat([{"role": "user", "content": "Reply with the single word: OK"}], temperature=0, max_tokens=200)
        print(green("works") + f"  -> model said: {r[:40]!r}")
    except LLMError as e:
        print(red("FAILED"))
        print("  ", e)
        print("  Tips: check OPENROUTER_API_KEY, the model id, and whether the free model is rate-limited (wait a minute).")
    if config.LANGSMITH_ENABLED:
        try:
            from langsmith import Client
            next(iter(Client().list_projects(limit=1)), None)
            print("Checking LangSmith... " + green("works"))
        except Exception as e:
            print("Checking LangSmith... " + red("FAILED") + f" ({str(e)[:120]})")
    else:
        print("LangSmith: no API key -> tracing disabled")


def save(result):
    OUT_DIR.mkdir(exist_ok=True)
    p = OUT_DIR / f"campaign_{datetime.now():%Y%m%d_%H%M%S}.md"
    p.write_text("# Marketing campaign\n\n" + render(result, markdown=True), encoding="utf-8")
    print(green(f"Saved -> {p}"))


def handle(text, state):
    agent.set_progress_callback(lambda m: print(dim(f"  ... {m}"), flush=True))
    try:
        res = agent.run_agent(text, state.get("brief"))
    except LLMError as e:
        print(red(f"\nSorry, the model call failed: {e}"))
        print("Please try again in a moment (free models are rate-limited).")
        return
    except Exception as e:  # never crash the chat loop
        print(red(f"\nUnexpected error: {type(e).__name__}: {e}"))
        return
    print(render(res))
    if res["status"] == "ok":
        state["brief"], state["last"] = res["brief"], res
        agent.post_feedback(res)
        if res.get("run_id"):
            print(dim(f"\n(LangSmith trace logged to project '{config.LANGSMITH_PROJECT}')"))
        print(dim("Type /save to keep this, or ask me to refine it."))


def interactive():
    banner()
    state = {}
    while True:
        try:
            text = input(bold("\nYou> ")).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break
        if not text:
            continue
        low = text.lower()
        if low in ("/exit", "/quit", "exit", "quit"):
            print("Bye!")
            break
        if low == "/help":
            print(HELP)
        elif low == "/new":
            state.clear()
            print("Started a fresh campaign.")
        elif low == "/save":
            save(state["last"]) if state.get("last") else print("Nothing to save yet.")
        elif low == "/check":
            check()
        elif low.startswith("/eval"):
            import evaluate
            parts = low.split()
            lim = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
            (evaluate.run_langsmith if config.LANGSMITH_ENABLED else evaluate.run_local)(lim)
        else:
            handle(text, state)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", help="run a single request and exit")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--eval", action="store_true")
    ap.add_argument("--local", action="store_true", help="with --eval: don't upload to LangSmith")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()

    if not config.OPENROUTER_API_KEY and not config.MOCK_LLM:
        print(red("OPENROUTER_API_KEY not found."), "Add it to the .env file next to main.py (see .env.example).")
        sys.exit(1)
    if a.check:
        return check()
    if a.eval:
        import evaluate
        return (evaluate.run_local if a.local or not config.LANGSMITH_ENABLED else evaluate.run_langsmith)(a.limit)
    if a.once:
        banner()
        return handle(a.once, {})
    interactive()


if __name__ == "__main__":
    main()
