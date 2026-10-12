"""Sentiment-derived urgency heuristic; independent of the category classifier."""

from functools import lru_cache

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


@lru_cache(maxsize=1)
def _analyzer() -> SentimentIntensityAnalyzer:
    return SentimentIntensityAnalyzer()


def ensure_urgency_ready() -> None:
    """Load VADER resources during application startup."""
    _analyzer()


def score_urgency(text: str) -> dict[str, float | int | str]:
    """Map VADER compound polarity to a 0-100 urgency score and level.

    Neutral language stays low; more negative sentiment raises urgency and more
    positive sentiment lowers it. Thresholds remain a transparent heuristic.
    """
    compound = _analyzer().polarity_scores(str(text))["compound"]
    if abs(compound) <= 0.10:
        score = 20
    else:
        score = round((1.0 - compound) * 50)
    score = max(0, min(100, score))
    level = "High" if score >= 70 else "Medium" if score >= 35 else "Low"
    return {
        "score": score,
        "level": level,
        "sentiment_compound": round(compound, 4),
    }
