import pytest

from pinterest_automation.api import openrouter as orr
from pinterest_automation.config.settings import settings


@pytest.fixture(autouse=True)
def _isolated_llm_env():
    # .env may set LLM_PROVIDERS; tests that exercise the legacy single-provider
    # path monkeypatch the LLM_* / OPENROUTER_* fields, so clear the pool and
    # reset failover health between tests to avoid cross-test contamination.
    original = settings.llm_providers
    settings.llm_providers = ""
    orr._health.clear()
    orr._idx = 0
    yield
    settings.llm_providers = original
