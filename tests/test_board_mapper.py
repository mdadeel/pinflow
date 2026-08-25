import pytest

BOARDS = [
    {"id": "1", "name": "Anime Board"},
    {"id": "2", "name": "Nature Photos"},
    {"id": "3", "name": "phone backgrounds"},
]


def test_manual_override_wins():
    from pinterest_automation.services.board_mapper import map_board
    assert map_board("Anything", BOARDS, overrides={"Anything": "9"}) == "9"


def test_exact_match_case_insensitive():
    from pinterest_automation.services.board_mapper import map_board
    assert map_board("Phone Backgrounds", BOARDS) == "3"


def test_keyword_overlap():
    from pinterest_automation.services.board_mapper import map_board
    assert map_board("Best Anime Wallpapers", BOARDS) == "1"


def test_no_match_returns_none():
    from pinterest_automation.services.board_mapper import map_board
    assert map_board("Cooking Recipes", BOARDS) is None


def test_empty_recommended_returns_none():
    from pinterest_automation.services.board_mapper import map_board
    assert map_board("", BOARDS) is None


def test_settings_parse_overrides_json(monkeypatch):
    monkeypatch.setenv("BOARD_OVERRIDES", '{"Couple Wallpapers": "123"}')
    from pinterest_automation.config.settings import Settings
    s = Settings(_env_file=None)
    assert s.board_overrides == {"Couple Wallpapers": "123"}


def test_stopwords_do_not_match():
    from pinterest_automation.services.board_mapper import map_board
    # 'Best' alone should not match anything meaningful; no overlap with any board beyond stopwords
    assert map_board("The Best", BOARDS) is None
