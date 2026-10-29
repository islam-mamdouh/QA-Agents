"""Risk-based testing: every story gets a risk score = impact x likelihood (each 1-5).

The story analysis agent rates impact and likelihood; the score and level are calculated here,
so they are always consistent. Higher-risk stories are tested first and more deeply.
"""
LEVELS = ((15, "high"), (8, "medium"), (1, "low"))  # score >= 15 high, >= 8 medium, else low


def risk_level(score: int) -> str:
    return next(name for limit, name in LEVELS if score >= limit)


def rate(impact, likelihood) -> dict:
    impact, likelihood = int(impact), int(likelihood)
    score = impact * likelihood
    return {"impact": impact, "likelihood": likelihood, "score": score, "level": risk_level(score)}


def check_risk(data: dict) -> None:
    """Validator (fire-back): every analysed story needs impact and likelihood from 1 to 5."""
    for story in data.get("stories", []):
        for field in ("risk_impact", "risk_likelihood"):
            value = story.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 5:
                raise ValueError(f"story '{story.get('key')}': '{field}' must be a whole number from 1 to 5")
