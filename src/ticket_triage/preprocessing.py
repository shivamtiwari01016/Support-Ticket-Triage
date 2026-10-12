"""Explainable text cleaning and linguistic feature extraction."""

from functools import lru_cache
import re
import unicodedata

import spacy

from ticket_triage.config import SPACY_MODEL

URL_PATTERN = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
NON_WORD_PATTERN = re.compile(r"[^A-Za-z0-9\s'-]")
NUMBER_PATTERN = re.compile(r"\b\d+\b")
WHITESPACE_PATTERN = re.compile(r"\s+")
LATIN_TOKEN_PATTERN = re.compile(r"[A-Za-z]+\Z")


def clean_text(text: str) -> str:
    """Normalize punctuation and strip URLs, emails, and non-Latin noise while preserving valid words."""
    cleaned = URL_PATTERN.sub(" ", str(text))
    cleaned = EMAIL_PATTERN.sub(" ", cleaned)
    cleaned = cleaned.replace("’", "'").replace("‘", "'").replace("–", "-").replace("—", "-")
    cleaned = unicodedata.normalize("NFKD", cleaned)
    cleaned = "".join(ch for ch in cleaned if not unicodedata.combining(ch))
    cleaned = NON_WORD_PATTERN.sub(" ", cleaned)
    cleaned = NUMBER_PATTERN.sub(" ", cleaned)
    cleaned = cleaned.replace("' ", " ").replace(" '", " ")
    return WHITESPACE_PATTERN.sub(" ", cleaned).strip()


def script_valid_tokens(tokens: list[str]) -> list[str]:
    """Keep alphabetic ASCII (Latin-script) tokens only."""
    return [
        token
        for token in tokens
        if token.isascii() and LATIN_TOKEN_PATTERN.fullmatch(token) is not None
    ]


@lru_cache(maxsize=1)
def _get_nlp():
    try:
        return spacy.load(SPACY_MODEL)
    except OSError as error:
        raise RuntimeError(
            f"spaCy model {SPACY_MODEL} is required. Install it with "
            f"`python -m spacy download {SPACY_MODEL}`."
        ) from error


def ensure_nlp_ready() -> None:
    """Load the configured spaCy model during application startup."""
    _get_nlp()


def extract_entities(text: str) -> list[dict[str, str]]:
    """Extract date, amount, and organization entities from the original text."""
    document = _get_nlp()(str(text))
    relevant_labels = {"DATE", "MONEY", "ORG"}
    return [
        {"text": entity.text, "label": entity.label_}
        for entity in document.ents
        if entity.label_ in relevant_labels
    ]


def extract_features(text: str) -> list[str]:
    """Return lemmatized tokens, noun-phrase markers, and NER markers.

    TfidfVectorizer adds unigram and bigram terms over this feature sequence.
    """
    original_text = str(text)
    entities = extract_entities(original_text)
    document = _get_nlp()(clean_text(original_text))

    tokens: list[str] = []
    for token in document:
        if token.is_stop or not token.is_alpha or not token.text.isascii():
            continue
        lemma = token.lemma_.lower().strip()
        if lemma and not token.is_stop:
            tokens.extend(script_valid_tokens([lemma]))

    phrase_features: list[str] = []
    for chunk in document.noun_chunks:
        phrase_tokens = [
            token.lemma_.lower().strip()
            for token in chunk
            if not token.is_stop and token.is_alpha and token.text.isascii()
        ]
        phrase_tokens = script_valid_tokens(phrase_tokens)
        if phrase_tokens:
            phrase_features.append("phrase_" + "_".join(phrase_tokens))

    entity_features = [
        f"entity_{entity['label'].lower()}" for entity in entities
    ]
    return tokens + phrase_features + entity_features
