from llm.json_util import parse_json_blob


def test_parse_json_strips_fence():
    raw = """```json
[{"a": 1}]
```"""
    assert parse_json_blob(raw) == [{"a": 1}]


def test_parse_plain_json():
    assert parse_json_blob('{"ordered":[]}') == {"ordered": []}
