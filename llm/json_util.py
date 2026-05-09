"""JSON helpers (no Gemini import — safe for unit tests)."""

import json
import re


def parse_json_blob(text: str):
    """Model output sometimes wraps JSON in markdown fences."""
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", t)
    if fence:
        t = fence.group(1).strip()
    return json.loads(t)
