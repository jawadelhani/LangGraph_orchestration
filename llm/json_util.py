"""JSON helpers (no Gemini import — safe for unit tests)."""

import json
import re


def parse_json_blob(text: str):
    """Model output sometimes wraps JSON in markdown fences or conversational text."""
    t = text.strip()
    
    # 1. Try markdown fences
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", t)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 2. Try raw parse
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass

    # 3. Try to extract first `{` to last `}`
    brace_match = re.search(r"(\{[\s\S]*\})", t)
    if brace_match:
        try:
            return json.loads(brace_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 4. Try to extract first `[` to last `]`
    bracket_match = re.search(r"(\[[\s\S]*\])", t)
    if bracket_match:
        try:
            return json.loads(bracket_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Raise the original error
    return json.loads(t)

