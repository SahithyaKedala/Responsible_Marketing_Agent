"""Offline fake model used ONLY for self-testing (MOCK_LLM=1). Not used in normal runs."""
import json

_calls = {"gen": 0}


def respond(messages):
    system = messages[0]["content"]
    user = messages[-1]["content"]
    if system.startswith("TASK: INTAKE"):
        low = user.lower()
        if "hello" in low and "write" not in low:
            return json.dumps({"intent": "chat", "reply": "Hi! Tell me what you'd like to promote.", "brief": {}, "unethical_requests": [], "missing": []})
        unethical = ["fake testimonials", "guaranteed results"] if "fake" in low else []
        return json.dumps({"intent": "refine" if "shorter" in low else "generate", "reply": "",
                           "brief": {"product": "soy candles", "description": "handmade candles", "audience": "young professionals",
                                     "channels": ["Instagram", "Email"], "tone": "warm", "goal": "sales",
                                     "key_facts": ["8-hour burn time"], "constraints": [], "num_ideas": 2},
                           "unethical_requests": unethical, "missing": []})
    if system.startswith("TASK: GENERATE"):
        _calls["gen"] += 1
        bad = "Last chance! Only 3 left - doctors recommend our candles, 100% guaranteed."
        return json.dumps({"headlines": ["Light up your evening", bad],
                           "copy": [{"channel": "Instagram", "headline": "Slow evenings", "body": "Handmade soy candles with an 8-hour burn time.", "cta": "Shop now"}],
                           "campaign_ideas": [{"name": "Evening Ritual", "concept": "Show real routines.", "channels": ["Instagram"], "sample_post": "Our evening ritual.", "ethical_note": "Honest."}],
                           "claims": []})
    if system.startswith("TASK: REVISE"):
        return json.dumps({"headlines": ["Light up your evening", "Handmade, slow-burning calm"],
                           "copy": [{"channel": "Instagram", "headline": "Slow evenings", "body": "Handmade soy candles with an 8-hour burn time.", "cta": "Shop the collection"}],
                           "campaign_ideas": [{"name": "Evening Ritual", "concept": "Show real routines.", "channels": ["Instagram"], "sample_post": "Our evening ritual.", "ethical_note": "Honest."}],
                           "claims": []})
    if system.startswith("TASK: ETHICS_AUDIT") or system.startswith("TASK: EVAL_ETHICS"):
        return json.dumps({"violations": []})
    if system.startswith("TASK: SCORECARD"):
        return json.dumps({"personas": [{"name": "Asha", "profile": "28, designer", "attention": 7, "interest": 7, "trust": 8, "click_prob": 0.12, "purchase_intent": 0.3, "would_convert": True, "objection": "price"},
                                        {"name": "Ravi", "profile": "skeptic", "attention": 5, "interest": 4, "trust": 6, "click_prob": 0.05, "purchase_intent": 0.1, "would_convert": False, "objection": "why not cheaper"}],
                           "quality": {"clarity": 8, "relevance": 8, "persuasiveness": 7, "originality": 6, "brand_fit": 8, "cta_strength": 7, "strengths": ["clear"], "improvements": ["add social proof from real customers"]}})
    if system.startswith("TASK: QUALITY_JUDGE"):
        return json.dumps({"clarity": 8, "relevance_to_request": 8, "persuasiveness": 7, "originality": 6, "cta_strength": 7, "comment": "ok"})
    return "OK"
