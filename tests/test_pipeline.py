from pathlib import Path

import pandas as pd
import pytest

from ticket_triage.data import category_from_label, load_ticket_data
from ticket_triage.model import build_classifier
from ticket_triage.preprocessing import (
    clean_text,
    extract_entities,
    extract_features,
    script_valid_tokens,
)
from ticket_triage.train import train_and_evaluate
from ticket_triage.urgency import score_urgency


def test_clean_text_removes_requested_artifacts():
    cleaned = clean_text("Email me at user@example.com: https://example.com/a?x=3 😊 Bad, 42!")
    assert cleaned == "Email me at Bad"


def test_clean_text_preserves_valid_apostrophes_and_accents():
    cleaned = clean_text("I don't like café and résumé issues.")
    assert "don't" in cleaned.lower()
    assert "cafe" in cleaned.lower()
    assert "resume" in cleaned.lower()


def test_script_validation_keeps_ascii_latin_tokens():
    assert script_valid_tokens(["account", "café", "123", "登录"]) == ["account"]


def test_clean_text_does_not_drop_valid_latin_words_with_accents():
    assert clean_text("My café account is unavailable.") == "My cafe account is unavailable"


def test_feature_extraction_adds_lemmatized_noun_phrase():
    features = extract_features("The internet connections are failing.")

    assert "connection" in features
    assert "phrase_internet_connection" in features


def test_ner_extracts_date_money_and_organization():
    entities = extract_entities("Microsoft charged $250 on March 15, 2026.")

    assert {"DATE", "MONEY", "ORG"} <= {entity["label"] for entity in entities}


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Billing inquiry", "Billing"),
        ("Refund request", "Billing"),
        ("Technical issue", "Technical Support"),
        ("Cancellation request", "Account"),
        ("Product inquiry", "General"),
    ],
)
def test_dataset_type_mapping(label, expected):
    assert category_from_label(label) == expected


def test_unknown_category_fails_loudly():
    with pytest.raises(ValueError, match="Unsupported"):
        category_from_label("unreviewed ticket kind")


def test_loader_combines_subject_and_description(tmp_path: Path):
    csv_path = tmp_path / "tickets.csv"
    pd.DataFrame(
        {
            "Ticket Type": ["Billing inquiry", "Technical issue"],
            "Ticket Subject": ["Payment", "Network"],
            "Ticket Description": ["Refund needed", "Connection failed"],
        }
    ).to_csv(csv_path, index=False)

    tickets = load_ticket_data(csv_path)

    assert tickets["text"].tolist() == [
        "Payment Refund needed",
        "Network Connection failed",
    ]
    assert tickets["category"].tolist() == ["Billing", "Technical Support"]


def test_classifier_is_class_weighted_logistic_regression():
    classifier = build_classifier()
    logistic = classifier.named_steps["classifier"]
    assert logistic.class_weight == "balanced"
    assert logistic.__class__.__name__ == "LogisticRegression"
    assert classifier.named_steps["tfidf"].ngram_range == (1, 2)


def test_negative_sentiment_has_higher_urgency_score():
    negative = score_urgency("This is awful, broken, and completely unacceptable")
    positive = score_urgency("This is excellent, wonderful, and completely resolved")
    neutral = score_urgency("The meeting is scheduled for tomorrow at 3pm")

    assert 0 <= negative["score"] <= 100
    assert negative["score"] > positive["score"]
    assert neutral["level"] == "Low"


def test_training_metrics_include_cv_and_reproducibility_metadata(tmp_path: Path):
    csv_path = tmp_path / "tickets.csv"
    rows = [
        {"Ticket Type": "Billing inquiry", "Ticket Subject": f"Invoice {idx}", "Ticket Description": "Refund needed for duplicate charge"}
        for idx in range(1, 5)
    ]
    rows += [
        {"Ticket Type": "Technical issue", "Ticket Subject": f"Crash {idx}", "Ticket Description": "Application keeps failing at startup"}
        for idx in range(1, 5)
    ]
    rows += [
        {"Ticket Type": "Cancellation request", "Ticket Subject": f"Cancel {idx}", "Ticket Description": "Need to cancel account and subscription"}
        for idx in range(1, 5)
    ]
    rows += [
        {"Ticket Type": "Product inquiry", "Ticket Subject": f"Question {idx}", "Ticket Description": "Need onboarding and pricing details"}
        for idx in range(1, 5)
    ]
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    metrics = train_and_evaluate(csv_path, tmp_path / "model.joblib")

    assert "cv_macro_f1_mean" in metrics
    assert "cv_macro_f1_std" in metrics
    assert "cv_macro_f1_scores" in metrics
    assert "git_sha" in metrics
    assert isinstance(metrics["git_sha"], str)
