"""Central configuration. Reads your existing .env file (several variable names accepted)."""
import os
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

_HERE = Path(__file__).resolve().parent
load_dotenv(_HERE / ".env")                       # .env next to this file
load_dotenv(find_dotenv(usecwd=True))              # or in the current folder


def _first(*names, default=None):
    for n in names:
        v = os.getenv(n)
        if v and v.strip():
            return v.strip().strip('"').strip("'")
    return default


OPENROUTER_API_KEY = _first("OPENROUTER_API_KEY", "OPENROUTER_KEY", "OPEN_ROUTER_API_KEY")
OPENROUTER_BASE_URL = _first("OPENROUTER_BASE_URL", default="https://openrouter.ai/api/v1")
MODEL = _first("OPENROUTER_MODEL", "MODEL_NAME", "MODEL", "LLM_MODEL",
               default="nvidia/nemotron-3-ultra-550b-a55b:free")

LANGSMITH_API_KEY = _first("LANGSMITH_API_KEY", "LANGCHAIN_API_KEY")
LANGSMITH_PROJECT = _first("LANGSMITH_PROJECT", "LANGCHAIN_PROJECT", default="ethical-marketing-agent")

# Tuning knobs (all optional in .env)
MAX_TOKENS = int(_first("MAX_TOKENS", default="8000"))          # reasoning models need headroom
REQUEST_TIMEOUT = float(_first("REQUEST_TIMEOUT", default="180"))
MAX_RETRIES = int(_first("LLM_MAX_RETRIES", default="4"))
REASONING_EFFORT = _first("REASONING_EFFORT")                    # e.g. low / medium / high (optional)
MAX_REVISIONS = int(_first("MAX_REVISIONS", default="2"))
MOCK_LLM = _first("MOCK_LLM", default="0") == "1"                # offline self-test only

LANGSMITH_ENABLED = bool(LANGSMITH_API_KEY) and _first("DISABLE_TRACING", default="0") != "1"


def apply_langsmith_env():
    """Export the variables the LangSmith SDK reads."""
    if LANGSMITH_ENABLED:
        os.environ["LANGSMITH_API_KEY"] = LANGSMITH_API_KEY
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGSMITH_PROJECT"] = LANGSMITH_PROJECT
        os.environ["LANGCHAIN_PROJECT"] = LANGSMITH_PROJECT
    else:
        os.environ["LANGSMITH_TRACING"] = "false"
        os.environ["LANGCHAIN_TRACING_V2"] = "false"


apply_langsmith_env()
