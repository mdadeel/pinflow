def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "test-model")
    monkeypatch.setenv("BATCH_SIZE", "50")
    monkeypatch.setenv("POST_HOURS", "9,12")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    from pinterest_automation.config.settings import Settings
    s = Settings(_env_file=None)
    assert s.openrouter_model == "test-model"
    assert s.batch_size == 50
    assert s.post_hours == [9, 12]
    assert s.openrouter_api_key == ""
