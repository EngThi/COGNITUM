"""Shared utilities for COGNITUM core modules."""

from __future__ import annotations

import os
import re

from google import genai

from cognitum.config import settings


def clean_json_text(text: str) -> str:
    """Remove Markdown fences and extract the most likely JSON object/array."""
    cleaned = (text or "").strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()

    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    first_bracket = cleaned.find("[")
    last_bracket = cleaned.rfind("]")

    if first_brace != -1 and last_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        return cleaned[first_brace : last_brace + 1]
    if first_bracket != -1 and last_bracket != -1:
        return cleaned[first_bracket : last_bracket + 1]
    return cleaned


_genai_client: genai.Client | None = None


def get_genai_client() -> genai.Client:
    """Return a singleton Gemini client configured from env/settings."""
    global _genai_client
    if _genai_client is None:
        api_key = os.getenv("GEMINI_API_KEY") or settings.gemini_api_key
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment or config.")
        _genai_client = genai.Client(api_key=api_key)
    return _genai_client


def truncate(text: str, max_chars: int = 2500) -> str:
    """Truncate long text with a standard suffix."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... [TRUNCATED] ..."
