"""Deterministic ethics checks (fast, free, explainable). They run BEFORE and AFTER the LLM auditor."""
import re

# (category, severity, regex, why, fix)
_OUTPUT_RULES = [
    ("false_claim", "high",
     r"\b(100\s*%\s*(guarantee\w*|safe|effective|natural|success\w*|results?)|guaranteed (results?|returns?|to work|success|weight ?loss|profit|income)|"
     r"risk[- ]free|no side[- ]effects?|miracle|cures?\b|cured\b|works for everyone|proven to (cure|heal|work for everyone))",
     "Absolute or guaranteed claim that cannot be verified.",
     "Use honest, qualified language (e.g. 'designed to help', 'many users find')."),
    ("unverified_superlative", "medium",
     r"\b(world'?s (best|finest|leading|#1)|#1 (rated|choice|brand|in)|number[- ]one (rated|brand|choice)|best in (the )?(world|class|market)|unbeatable|unrivall?ed)\b",
     "Superlative claim without supporting evidence.",
     "Describe a concrete, true benefit instead of 'best'."),
    ("fabricated_proof", "high",
     r"\b(clinically (proven|tested)|doctor[- ]recommended|doctors (recommend|agree|love)|scientifically proven|award[- ]winning|as seen (on|in)|"
     r"(thousands|millions) of (happy |satisfied )?(customers|users|people)|trusted by (thousands|millions)|\d[\d,]*\+? (happy|satisfied) (customers|users))",
     "Social proof / authority claim not supplied by the brand.",
     "Remove it or add a placeholder like [ADD: verified stat]."),
    ("fabricated_testimonial", "high",
     r"[\"\u201c][^\"\u201d]{15,}[\"\u201d]\s*(?:[\u2014\u2013~]|--|-)\s*[A-Z][a-z]+",
     "Looks like an invented customer testimonial.",
     "Use only real, consented testimonials, or ask customers for reviews."),
    ("false_scarcity", "high",
     r"\b(only \d+ (left|remaining|spots?|units?|pieces?|seats?)|(almost|nearly) (gone|sold out)|selling out fast|while (stocks?|supplies) last)",
     "Scarcity claim not backed by stated facts.",
     "Drop the scarcity claim unless real stock data is provided."),
    ("fear_shame", "high",
     r"\b(you'?ll regret|you will regret|don'?t be (a )?(loser|fool)|you'?re (failing|falling behind)|ashamed|left behind|"
     r"your (family|kids|children) (will|could|might) (suffer|die|be in danger)|can you afford (not|to ignore)|scared? (of|that) )",
     "Uses fear, shame or guilt to pressure the reader.",
     "Lead with a positive, honest benefit instead."),
    ("confirmshaming", "medium",
     r"no thanks?,? i (don'?t|do not) (want|like|care)|i'?d rather (stay|be|pay|lose)",
     "Confirmshaming (guilt-tripping the 'no' option).",
     "Use a neutral decline option."),
    ("discrimination", "high",
     r"\b(whites? only|blacks? only|no (blacks?|whites?|muslims?|hindus?|christians?|jews|gays?|immigrants?|foreigners?|disabled|handicapped|elderly|families|kids|children)\b|"
     r"not for (the )?(old|elderly|disabled|poor|women|men)\b|(only|just) for (the )?(young|white|able[- ]bodied|healthy|rich)\b|too old|"
     r"(women|men|girls|boys|old people|seniors|elderly) (can'?t|cannot|are (too|bad at|naturally|not able))\b)",
     "Excludes or stereotypes people by a protected attribute.",
     "Target by need or interest, never by exclusion or stereotype."),
    ("financial_health_hype", "high",
     r"\b(get rich|double your money|guaranteed (profit|income|returns?)|lose \d+ ?(lbs?|pounds?|kg|kilos?) in \d+ (days?|weeks?)|make \$?\d[\d,]* (a|per) (day|week|month) (easily|guaranteed))",
     "Unrealistic health or financial promise.",
     "Avoid numeric outcome promises; describe the product honestly."),
]

# Urgency wording is allowed only if the brief contains a REAL deadline.
_URGENCY = (
    "false_urgency", "high",
    r"\b(last chance|hurry|act now|don'?t miss out|before it'?s too late|offer expires (soon|tonight|in)|today only|ends (tonight|soon|in \d+))",
    "Pressure-based urgency without a real deadline in the brief.",
    "Remove pressure wording or state the real deadline plainly.",
)
_DEADLINE = re.compile(
    r"(ends?|until|through|valid (till|until)|expires?|deadline|offer ends)\W+(on\W+)?"
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{1,2}\s*(st|nd|rd|th)?\s*(of\s+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)|\d{1,2}[/-]\d{1,2}|\d{4}-\d{2}-\d{2}|\d{1,2}(st|nd|rd|th))", re.I)

# Things the USER asks for that we refuse to do.
_REQUEST_RULES = [
    (r"\b(fake|made[- ]up|fabricat\w+|invent\w*|false)\s+(customer\s+)?(reviews?|testimonials?|stat(istic)?s?|numbers?|quotes?|endorsements?|awards?|ratings?)",
     "fake reviews / testimonials / statistics"),
    (r"\b(fake|false|artificial)\s+(urgency|scarcity|deadline)|say (that )?(only|just) \d+ (are |is )?left|pretend (it'?s|there'?s|that)",
     "false urgency / scarcity"),
    (r"\bguarantee(d)?\b.{0,40}\b(cure|lose|weight|profit|returns?|income|rich)|\b(cure|lose \d+|double (your )?money|get rich|risk[- ]free)\b",
     "guaranteed health / financial outcomes"),
    (r"\bmake (them|people|customers|users|elderly|seniors|parents|women|men|kids)?\s*(feel )?(scared|afraid|guilty|ashamed|worthless|insecure)\b|\bscare (them|people|customers)|guilt[- ]trip|shame (them|people)",
     "fear / guilt / shame manipulation"),
    (r"\b(only for|just for|no)\s+(the\s+)?(young|white|whites|blacks?|muslims?|hindus?|christians?|jews|gays?|immigrants?|foreigners?|disabled|handicapped|families|elderly|old people|women|men)\b|whites? only",
     "discriminatory targeting / exclusion"),
    (r"\bhide\s+(the\s+)?(fees?|costs?|price|terms|conditions|renewal|subscription)|without (them )?(knowing|noticing)",
     "hiding material information"),
    (r"\b(lie|lies|lying|deceive|deceptive|mislead\w*|trick (them|people|customers))\b",
     "deceptive messaging"),
    (r"\b(exploit|take advantage of)\b.{0,30}\b(elderly|seniors|kids|children|vulnerable|desperate|poor|sick)",
     "exploiting vulnerable people"),
]


def _norm(s):
    return re.sub(r"\s+", " ", (s or "").lower())


def scan(text: str, brief_text: str = "") -> list:
    """Return a list of violations found in the generated marketing text."""
    found, brief_n = [], _norm(brief_text)
    has_deadline = bool(_DEADLINE.search(brief_text or ""))
    rules = list(_OUTPUT_RULES) + [_URGENCY]
    for cat, sev, pat, why, fix in rules:
        for m in re.finditer(pat, text or "", re.I):
            quote = m.group(0).strip()
            if _norm(quote) in brief_n:                    # user supplied this fact themselves
                continue
            if cat == "false_urgency" and has_deadline:    # real deadline exists
                continue
            found.append({"category": cat, "severity": sev, "quote": quote,
                          "why": why, "fix": fix, "source": "rules"})
    seen, unique = set(), []
    for v in found:
        k = (v["category"], _norm(v["quote"]))
        if k not in seen:
            seen.add(k)
            unique.append(v)
    return unique


def scan_request(text: str) -> list:
    """Spot unethical asks inside the USER's message. Returns human-readable labels."""
    labels = []
    for pat, label in _REQUEST_RULES:
        if re.search(pat, text or "", re.I) and label not in labels:
            labels.append(label)
    return labels


def ethics_score(violations: list) -> float:
    """0..1 score: each high violation costs 0.3, medium 0.1, low 0.05."""
    cost = {"high": 0.3, "medium": 0.1, "low": 0.05}
    return round(max(0.0, 1.0 - sum(cost.get(v.get("severity", "high"), 0.3) for v in violations)), 2)
