import json

import httpx
import pytest

VALID = {
    "title": "Aesthetic Anime Wallpaper for Phone with Dark Moody Vibes HD",
    "description": "x" * 320,
    "alt_text": "Dark moody anime wallpaper showing a lone figure at night.",
    "primary_keyword": "anime wallpaper",
    "secondary_keywords": [f"kw{i}" for i in range(12)],
    "tags": [f"tag{i}" for i in range(18)],
    "board": "Anime Wallpapers",
    "category": "Anime",
}
VALID_RAW = "```json\n" + json.dumps(VALID) + "\n```"


def test_parse_strips_fences():
    from pinterest_automation.services.seo_generator import parse_metadata
    m = parse_metadata(VALID_RAW)
    assert m.board == "Anime Wallpapers" and len(m.tags) == 18


def test_parse_accepts_plain_json():
    from pinterest_automation.services.seo_generator import parse_metadata
    m = parse_metadata(json.dumps(VALID))
    assert m.category == "Anime"


def test_parse_rejects_short_title():
    from pinterest_automation.services.seo_generator import parse_metadata, MetadataValidationError
    with pytest.raises(MetadataValidationError):
        parse_metadata(json.dumps(dict(VALID, title="too short")))


def test_parse_rejects_too_many_tags():
    from pinterest_automation.services.seo_generator import parse_metadata, MetadataValidationError
    with pytest.raises(MetadataValidationError):
        parse_metadata(json.dumps(dict(VALID, tags=[f"t{i}" for i in range(26)])))


def test_parse_rejects_garbage():
    from pinterest_automation.services.seo_generator import parse_metadata, MetadataValidationError
    with pytest.raises(MetadataValidationError):
        parse_metadata("not json at all")


def test_generate_success_first_try(monkeypatch, tmp_path):
    from pinterest_automation.services import seo_generator as sg
    calls = []

    def fake_chat(messages):
        calls.append(messages)
        return VALID_RAW

    monkeypatch.setattr(sg, "chat", fake_chat)
    monkeypatch.setattr(sg, "image_data_url", lambda p: "data:image/png;base64,AAA")
    p = tmp_path / "i.png"; p.write_bytes(b"z")
    m = sg.generate_metadata(p)
    assert m.category == "Anime"
    assert len(calls) == 1
    # vision message shape: text part + image part
    content = calls[0][0]["content"]
    assert content[0]["type"] == "text" and content[1]["type"] == "image_url"


def test_generate_retries_once_with_feedback(monkeypatch, tmp_path):
    from pinterest_automation.services import seo_generator as sg
    calls = []

    def fake_chat(messages):
        calls.append(messages)
        if len(calls) == 1:
            return "garbage not json"
        return VALID_RAW

    monkeypatch.setattr(sg, "chat", fake_chat)
    monkeypatch.setattr(sg, "image_data_url", lambda p: "data:image/png;base64,AAA")
    p = tmp_path / "i.png"; p.write_bytes(b"z")
    assert sg.generate_metadata(p).board == "Anime Wallpapers"
    assert len(calls) == 2
    feedback_text = calls[1][0]["content"][0]["text"]
    assert "rejected" in feedback_text.lower()


def test_generate_raises_after_second_failure(monkeypatch, tmp_path):
    from pinterest_automation.services import seo_generator as sg
    monkeypatch.setattr(sg, "chat", lambda messages: "still garbage")
    monkeypatch.setattr(sg, "image_data_url", lambda p: "data:image/png;base64,AAA")
    p = tmp_path / "i.png"; p.write_bytes(b"z")
    with pytest.raises(sg.MetadataValidationError):
        sg.generate_metadata(p)


def test_prompt_file_contains_schema():
    from pinterest_automation.services.seo_generator import load_prompt
    text = load_prompt()
    assert "STRICT JSON" in text and "secondary_keywords" in text and "Anime Wallpapers" in text
