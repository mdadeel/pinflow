import logging

log = logging.getLogger(__name__)

STOPWORDS = {"for", "the", "and", "with", "best", "of", "a", "an", "in", "on"}


def _tokens(text: str) -> set[str]:
    return {w for w in text.lower().replace("-", " ").split() if w not in STOPWORDS}


def map_board(recommended: str, boards: list[dict],
              overrides: dict[str, str] | None = None) -> str | None:
    """Map an AI-recommended board name to a real Pinterest board id."""
    if not recommended:
        return None
    if overrides:
        lowered = {k.lower(): v for k, v in overrides.items()}
        hit = lowered.get(recommended.lower())
        if hit:
            return hit
    rec = _tokens(recommended)
    best_id: str | None = None
    best_score = 0
    for b in boards:
        name_tokens = _tokens(b.get("name", ""))
        if rec and name_tokens == rec:
            return b["id"]                       # exact token-set match
        score = len(name_tokens & rec)
        if score > best_score:
            best_id, best_score = b["id"], score
    if best_score:
        return best_id
    log.warning("no board mapping for recommendation %r", recommended)
    return None
