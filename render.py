"""Pretty terminal / markdown output."""
import os
import sys

os.system("")  # enables ANSI colours on Windows 10+ terminals
_COLOR = sys.stdout.isatty()


def c(text, code):
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def bold(t): return c(t, "1")
def green(t): return c(t, "32")
def red(t): return c(t, "31")
def yellow(t): return c(t, "33")
def cyan(t): return c(t, "36")
def dim(t): return c(t, "2")


def _bar(x, scale=1.0, width=10):
    n = int(round(max(0.0, min(1.0, x / scale)) * width))
    return "#" * n + "-" * (width - n)


def render(result: dict, markdown: bool = False) -> str:
    """Return the full answer as text (plain for terminal, no ANSI when markdown=True)."""
    H = (lambda t: f"## {t}") if markdown else (lambda t: "\n" + bold(cyan(f"=== {t} ===")))
    out = []
    st = result.get("status")
    if st in ("chat", "needs_info"):
        return result.get("message", "")

    b = result.get("brief") or {}
    out.append(H("BRIEF UNDERSTOOD"))
    out.append(f"Product : {b.get('product', '')}")
    out.append(f"Audience: {b.get('audience') or '(general)'}")
    out.append(f"Channels: {', '.join(b.get('channels', []))}")
    out.append(f"Tone    : {b.get('tone', '')}")
    if b.get("key_facts"):
        out.append("Facts   : " + "; ".join(b["key_facts"]))

    if result.get("declined"):
        out.append(H("ETHICS NOTICE"))
        out.append((yellow if not markdown else str)("I can't do the following, so I wrote honest alternatives instead:"))
        for d in result["declined"]:
            out.append(f"  - {d}")

    cont = result.get("content", {})
    out.append(H("HEADLINES"))
    for i, h in enumerate(cont.get("headlines", []), 1):
        out.append(f"{i}. {h}")

    out.append(H("AD COPY"))
    for x in cont.get("copy", []):
        out.append((bold(f"[{x['channel']}]") if not markdown else f"**[{x['channel']}]**"))
        if x.get("headline"): out.append(f"Headline: {x['headline']}")
        out.append(x.get("body", ""))
        if x.get("cta"): out.append(f"CTA: {x['cta']}")
        out.append("")

    out.append(H("CAMPAIGN IDEAS"))
    for i, x in enumerate(cont.get("campaign_ideas", []), 1):
        out.append(f"{i}. {x['name']}")
        out.append(f"   Concept : {x['concept']}")
        if x.get("channels"): out.append(f"   Channels: {', '.join(x['channels'])}")
        if x.get("sample_post"): out.append(f"   Sample  : {x['sample_post']}")
        if x.get("ethical_note"): out.append(f"   Ethics  : {x['ethical_note']}")
        out.append("")

    e = result.get("ethics", {})
    out.append(H("ETHICS REPORT"))
    ok = e.get("passed")
    badge = (green("PASSED") if ok else red("NEEDS HUMAN REVIEW")) if not markdown else ("PASSED" if ok else "NEEDS HUMAN REVIEW")
    out.append(f"Status: {badge}   score: {e.get('score', 0):.2f}/1.00   auto-revisions: {e.get('revisions', 0)}")
    for v in e.get("violations", []):
        out.append(f"  ! [{v['severity']}] {v['category']}: \"{v['quote']}\" - {v['why']}")
    for n in e.get("notes", []):
        out.append("  note: " + n)

    m, q = result.get("metrics") or {}, result.get("quality") or {}
    if q or m:
        out.append(H("QUALITY + SIMULATED CONVERSION"))
        if q:
            out.append(f"Quality overall : {q.get('overall', 0):.2f}  (clarity {q.get('clarity', '-')}, persuasiveness "
                       f"{q.get('persuasiveness', '-')}, originality {q.get('originality', '-')}, CTA {q.get('cta_strength', '-')})")
        if m:
            out.append(f"Avg click prob  : {m['avg_click_prob']:.0%}   [{_bar(m['avg_click_prob'])}]")
            out.append(f"Avg purchase int: {m['avg_purchase_intent']:.0%}   [{_bar(m['avg_purchase_intent'])}]")
            out.append(f"Sim. conversion : {m['sim_conversion_rate']:.0%} of {m['n_personas']} personas would convert")
            out.append(f"Avg trust       : {m['avg_trust']:.1f}/10")
        for p in result.get("personas", []):
            out.append(f"  - {p.get('name', '?')}: intent {float(p.get('purchase_intent', 0) or 0):.0%} | objection: {p.get('objection', '')}")
        for s in q.get("improvements", [])[:3]:
            out.append(f"  tip: {s}")
        out.append(dim("(Simulated by an LLM panel - a directional signal, not real market data.)") if not markdown
                   else "_(Simulated by an LLM panel - a directional signal, not real market data.)_")
    return "\n".join(out)
