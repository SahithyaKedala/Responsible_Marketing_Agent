"""Ethical Marketing Content Generator - agent pipeline.

intake -> input guard -> generate -> ethics review (rules + LLM auditor)
       -> revise loop -> scorecard (quality + simulated conversion)
Every step is traced to LangSmith when LANGSMITH_API_KEY is set.
"""
import json
from typing import Optional

import config
import ethics_rules
import prompts
from llm import LLMError, llm_json

try:
    from langsmith import traceable
    from langsmith.run_helpers import get_current_run_tree
except Exception:  # LangSmith not installed -> run untraced
    def traceable(*a, **k):
        def deco(f):
            return f
        return deco if not (a and callable(a[0])) else a[0]

    def get_current_run_tree():
        return None

DEFAULT_CHANNELS = ["Instagram", "Email", "Google Search Ad"]
_progress = lambda msg: None


def set_progress_callback(fn):
    global _progress
    _progress = fn or (lambda msg: None)


# ----------------------------------------------------------------- helpers
def _as_list(v):
    if v is None or v == "":
        return []
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    return [str(v).strip()]


def _num(v, lo, hi, default=0.0):
    try:
        return max(lo, min(hi, float(v)))
    except Exception:
        return default


def normalize_brief(b: dict) -> dict:
    b = b if isinstance(b, dict) else {}
    out = {
        "product": str(b.get("product") or "").strip(),
        "description": str(b.get("description") or "").strip(),
        "audience": str(b.get("audience") or "").strip(),
        "channels": _as_list(b.get("channels")) or list(DEFAULT_CHANNELS),
        "tone": str(b.get("tone") or "friendly, honest, professional").strip(),
        "goal": str(b.get("goal") or "increase awareness and conversions").strip(),
        "key_facts": _as_list(b.get("key_facts")),
        "constraints": _as_list(b.get("constraints")),
    }
    try:
        out["num_ideas"] = max(1, min(6, int(b.get("num_ideas") or 3)))
    except Exception:
        out["num_ideas"] = 3
    return out


def brief_text(brief: dict, user_input: str = "") -> str:
    """Everything the user actually told us (used to decide what counts as a 'provided fact')."""
    parts = [user_input, brief.get("product", ""), brief.get("description", ""),
             " ".join(brief.get("key_facts", [])), " ".join(brief.get("constraints", []))]
    return " ".join(p for p in parts if p)


def normalize_content(c: dict) -> dict:
    c = c if isinstance(c, dict) else {}

    def s(x):
        return str(x).strip() if x is not None else ""

    copy = []
    for item in c.get("copy") or []:
        if isinstance(item, dict):
            copy.append({k: s(item.get(k)) for k in ("channel", "headline", "body", "cta")})
        elif item:
            copy.append({"channel": "", "headline": "", "body": s(item), "cta": ""})
    ideas = []
    for item in c.get("campaign_ideas") or []:
        if isinstance(item, dict):
            ideas.append({"name": s(item.get("name")), "concept": s(item.get("concept")),
                          "channels": _as_list(item.get("channels")),
                          "sample_post": s(item.get("sample_post")),
                          "ethical_note": s(item.get("ethical_note"))})
    claims = []
    for item in c.get("claims") or []:
        if isinstance(item, dict):
            claims.append({"claim": s(item.get("claim")), "basis": s(item.get("basis"))})
    return {"headlines": _as_list(c.get("headlines")), "copy": copy,
            "campaign_ideas": ideas, "claims": claims}


def consumer_text(c: dict) -> str:
    """Only the text a customer could actually see (used for ethics scanning and evaluation)."""
    lines = list(c.get("headlines", []))
    for x in c.get("copy", []):
        lines += [x.get("headline", ""), x.get("body", ""), x.get("cta", "")]
    for x in c.get("campaign_ideas", []):
        lines += [x.get("name", ""), x.get("concept", ""), x.get("sample_post", "")]
    return "\n".join(l for l in lines if l)


# ------------------------------------------------------------------- steps
@traceable(name="intake", run_type="chain")
def intake(user_input: str, prev_brief: Optional[dict]) -> dict:
    user = ("Previous brief (null if none):\n" + json.dumps(prev_brief) +
            "\n\nUser message:\n" + user_input)
    return llm_json(prompts.INTAKE_SYSTEM, user, temperature=0.2, max_tokens=3000)


@traceable(name="generate_content", run_type="chain")
def generate(brief: dict, declined: list) -> dict:
    user = "BRIEF:\n" + json.dumps(brief, ensure_ascii=False, indent=1)
    if declined:
        user += ("\n\nThe user asked for things that are NOT allowed: " + "; ".join(declined) +
                 ".\nDo not do them. Produce honest alternatives that still serve the goal.")
    return normalize_content(llm_json(prompts.GENERATOR_SYSTEM, user, temperature=0.8))


@traceable(name="ethics_review", run_type="chain")
def ethics_review(content: dict, brief: dict, user_input: str) -> dict:
    text = consumer_text(content)
    violations = ethics_rules.scan(text, brief_text(brief, user_input))
    notes = []
    try:
        user = ("KEY_FACTS (verified): " + json.dumps(brief.get("key_facts", []), ensure_ascii=False) +
                "\n\nCONTENT:\n" + text)
        data = llm_json(prompts.AUDITOR_SYSTEM, user, temperature=0.0, max_tokens=3000)
        seen = {v["quote"].lower() for v in violations}
        for v in data.get("violations") or []:
            if not isinstance(v, dict):
                continue
            q = str(v.get("quote", "")).strip()
            if not q or q.lower() in seen:
                continue
            sev = str(v.get("severity", "high")).lower()
            violations.append({"category": str(v.get("category", "other")),
                               "severity": sev if sev in ("high", "medium", "low") else "high",
                               "quote": q, "why": str(v.get("why", "")),
                               "fix": str(v.get("fix", "")), "source": "llm_auditor"})
    except LLMError as e:
        notes.append(f"LLM auditor unavailable ({e}); rule-based checks only.")
    high = [v for v in violations if v["severity"] == "high"]
    return {"passed": not high, "score": ethics_rules.ethics_score(violations),
            "violations": violations, "notes": notes}


@traceable(name="revise_content", run_type="chain")
def revise(content: dict, violations: list, brief: dict) -> dict:
    user = ("BRIEF:\n" + json.dumps(brief, ensure_ascii=False) +
            "\n\nVIOLATIONS TO FIX:\n" + json.dumps(
                [{k: v[k] for k in ("category", "quote", "why", "fix")} for v in violations],
                ensure_ascii=False, indent=1) +
            "\n\nCONTENT:\n" + json.dumps(content, ensure_ascii=False))
    return normalize_content(llm_json(prompts.REVISE_SYSTEM, user, temperature=0.5))


def aggregate_scorecard(sc: dict) -> tuple:
    personas = [p for p in (sc.get("personas") or []) if isinstance(p, dict)]

    def avg(key, lo, hi):
        vals = [_num(p.get(key), lo, hi) for p in personas if p.get(key) is not None]
        return round(sum(vals) / len(vals), 3) if vals else 0.0

    def truthy(v):
        return v is True or str(v).strip().lower() in ("true", "yes", "1")

    metrics = {
        "n_personas": len(personas),
        "avg_attention": avg("attention", 0, 10),
        "avg_interest": avg("interest", 0, 10),
        "avg_trust": avg("trust", 0, 10),
        "avg_click_prob": avg("click_prob", 0, 1),
        "avg_purchase_intent": avg("purchase_intent", 0, 1),
        "sim_conversion_rate": round(sum(truthy(p.get("would_convert")) for p in personas) / len(personas), 3) if personas else 0.0,
    }
    q = sc.get("quality") if isinstance(sc.get("quality"), dict) else {}
    dims = ["clarity", "relevance", "persuasiveness", "originality", "brand_fit", "cta_strength"]
    scores = {d: _num(q.get(d), 1, 10) for d in dims if q.get(d) is not None}
    quality = {**scores, "overall": round(sum(scores.values()) / len(scores) / 10, 3) if scores else 0.0,
               "strengths": _as_list(q.get("strengths")), "improvements": _as_list(q.get("improvements"))}
    return metrics, quality, personas


@traceable(name="scorecard_simulation", run_type="chain")
def scorecard(content: dict, brief: dict) -> dict:
    user = ("BRIEF:\n" + json.dumps(brief, ensure_ascii=False) + "\n\nMARKETING COPY:\n" + consumer_text(content))
    return llm_json(prompts.SCORECARD_SYSTEM, user, temperature=0.6, max_tokens=4000)


# -------------------------------------------------------------------- main
@traceable(name="ethical_marketing_agent", run_type="chain")
def run_agent(user_input: str, prev_brief: Optional[dict] = None) -> dict:
    user_input = (user_input or "").strip()
    result = {"status": "ok", "message": "", "brief": prev_brief, "declined": [], "content": {},
              "final_text": "", "ethics": {}, "metrics": {}, "quality": {}, "personas": [], "run_id": ""}

    # 1) understand the request
    _progress("Understanding your request...")
    try:
        parsed = intake(user_input, prev_brief)
    except LLMError:
        parsed = {"intent": "generate", "brief": {"product": user_input}, "unethical_requests": []}
    intent = str(parsed.get("intent", "generate")).lower()
    if intent == "chat":
        result.update(status="chat", message=str(parsed.get("reply") or
                      "I write honest marketing copy and campaign ideas. Tell me what you want to promote!"))
        result["final_text"] = result["message"]
        return result

    brief = normalize_brief(parsed.get("brief"))
    if intent == "refine" and prev_brief and not brief["product"]:
        brief["product"] = prev_brief.get("product", "")
    if not brief["product"]:
        result.update(status="needs_info", message="What product or service should I write about? "
                      "(Optional: audience, channels, tone, key facts.)")
        result["final_text"] = result["message"]
        return result
    result["brief"] = brief

    # 2) input guard: refuse the unethical parts, keep the legitimate goal
    declined = _as_list(parsed.get("unethical_requests"))
    for label in ethics_rules.scan_request(user_input):
        if not any(label.split(" /")[0].split()[0].lower() in d.lower() for d in declined):
            declined.append(label)
    result["declined"] = declined
    if declined:
        _progress("Some requested tactics are unethical - I'll write honest alternatives.")

    # 3) generate
    _progress("Writing copy and campaign ideas...")
    content = generate(brief, declined)
    if not content["copy"] and not content["headlines"]:
        raise LLMError("The model returned no usable content. Please try again.")

    # 4) ethics review + revision loop
    review, revisions = {}, 0
    for attempt in range(config.MAX_REVISIONS + 1):
        _progress("Running ethics review..." if attempt == 0 else f"Re-checking ethics (revision {attempt})...")
        review = ethics_review(content, brief, user_input)
        fixable = [v for v in review["violations"] if v["severity"] in ("high", "medium")]
        if not fixable or attempt == config.MAX_REVISIONS:
            break
        _progress(f"Fixing {len(fixable)} ethics issue(s)...")
        try:
            content = revise(content, fixable, brief)
            revisions += 1
        except LLMError:
            break
    review["revisions"] = revisions
    result["content"] = content
    result["final_text"] = consumer_text(content)
    result["ethics"] = review

    # 5) quality + conversion simulation
    _progress("Simulating audience reaction and scoring quality...")
    try:
        metrics, quality, personas = aggregate_scorecard(scorecard(content, brief))
        result.update(metrics=metrics, quality=quality, personas=personas)
    except LLMError as e:
        result["metrics"] = {}
        result["quality"] = {}
        result["ethics"].setdefault("notes", []).append(f"Scorecard unavailable: {e}")

    # LangSmith metadata on the trace
    try:
        rt = get_current_run_tree()
        if rt is not None:
            result["run_id"] = str(rt.id)
            rt.add_metadata({"ethics_passed": review["passed"], "ethics_score": review["score"],
                             "revisions": revisions, "declined": bool(declined),
                             "sim_conversion_rate": result["metrics"].get("sim_conversion_rate"),
                             "quality_overall": result["quality"].get("overall")})
    except Exception:
        pass
    return result


def post_feedback(result: dict):
    """Attach scores to the LangSmith trace of a live run (best effort, never raises)."""
    if not (config.LANGSMITH_ENABLED and result.get("run_id") and result.get("ethics")):
        return
    try:
        from langsmith import Client
        client = Client()
        if hasattr(client, "flush"):
            client.flush()
        rid = result["run_id"]
        client.create_feedback(rid, key="ethics_compliance", score=result["ethics"].get("score", 0))
        if result.get("quality"):
            client.create_feedback(rid, key="content_quality", score=result["quality"].get("overall", 0))
        if result.get("metrics"):
            client.create_feedback(rid, key="simulated_conversion",
                                   score=result["metrics"].get("avg_purchase_intent", 0))
    except Exception:
        pass
