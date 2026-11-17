"""Thin, robust wrapper around OpenRouter (OpenAI-compatible API)."""
import json
import re
import time

import config


class LLMError(RuntimeError):
    pass


_client = None


def get_client():
    global _client
    if _client is None:
        if not config.OPENROUTER_API_KEY:
            raise LLMError("OPENROUTER_API_KEY not found. Put it in your .env file.")
        from openai import OpenAI
        c = OpenAI(
            base_url=config.OPENROUTER_BASE_URL,
            api_key=config.OPENROUTER_API_KEY,
            timeout=config.REQUEST_TIMEOUT,
            max_retries=0,
            default_headers={"HTTP-Referer": "http://localhost", "X-Title": "Ethical Marketing Agent"},
        )
        if config.LANGSMITH_ENABLED:
            try:  # logs every LLM call (tokens, latency) to LangSmith
                from langsmith.wrappers import wrap_openai
                c = wrap_openai(c)
            except Exception:
                pass
        _client = c
    return _client


_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)


def _clean(text: str) -> str:
    text = _THINK.sub("", text or "")
    return text.replace("</think>", "").strip()


def chat(messages, temperature=0.7, max_tokens=None) -> str:
    """Return the model's text. Retries on rate limits / empty answers / transient errors."""
    if config.MOCK_LLM:
        import mock_llm
        return mock_llm.respond(messages)

    max_tokens = max_tokens or config.MAX_TOKENS
    last_err, reasoning_fallback = None, ""
    for attempt in range(config.MAX_RETRIES + 1):
        try:
            kwargs = dict(model=config.MODEL, messages=messages,
                          temperature=temperature, max_tokens=max_tokens)
            if config.REASONING_EFFORT:
                kwargs["extra_body"] = {"reasoning": {"effort": config.REASONING_EFFORT}}
            resp = get_client().chat.completions.create(**kwargs)

            if not getattr(resp, "choices", None):
                err = getattr(resp, "error", None) or "provider returned no choices"
                raise LLMError(str(err))

            msg = resp.choices[0].message
            text = _clean(msg.content or "")
            if text:
                return text
            # Reasoning models sometimes spend the whole budget thinking -> retry with more room
            extra = getattr(msg, "model_extra", None) or {}
            reasoning_fallback = _clean(getattr(msg, "reasoning", None) or extra.get("reasoning") or "")
            max_tokens = min(int(max_tokens * 1.5), 32000)
            last_err = LLMError("model returned empty content")
        except LLMError as e:
            last_err = e
        except Exception as e:  # rate limit, timeout, network, 5xx ...
            last_err = e
            status = getattr(e, "status_code", None)
            if status in (400, 401, 403, 404):          # not worth retrying
                raise LLMError(f"OpenRouter error {status}: {e}") from e
        if attempt < config.MAX_RETRIES:
            time.sleep(min(3 * (2 ** attempt), 40))
    if reasoning_fallback:
        return reasoning_fallback
    raise LLMError(f"LLM call failed after retries: {last_err}")


def extract_json(text: str):
    """Pull the first valid JSON object out of messy model output."""
    if not text:
        return None
    text = re.sub(r"```(?:json)?", "", text)
    dec = json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        chunk = text[m.start():]
        try:
            obj, _ = dec.raw_decode(chunk)
            if isinstance(obj, dict):
                return obj
        except Exception:
            # try removing trailing commas on the best-effort span
            end = chunk.rfind("}")
            if end > 0:
                fixed = re.sub(r",\s*([}\]])", r"\1", chunk[: end + 1])
                try:
                    obj = json.loads(fixed)
                    if isinstance(obj, dict):
                        return obj
                except Exception:
                    pass
    return None


def llm_json(system: str, user: str, temperature=0.4, max_tokens=None, retries=2) -> dict:
    """Ask for JSON and make sure we get a dict back."""
    prompt = user
    for _ in range(retries + 1):
        text = chat([{"role": "system", "content": system},
                     {"role": "user", "content": prompt}],
                    temperature=temperature, max_tokens=max_tokens)
        data = extract_json(text)
        if data is not None:
            return data
        prompt = user + "\n\nIMPORTANT: your previous reply was not valid JSON. Reply with ONE valid JSON object only."
    raise LLMError("Model did not return valid JSON.")
