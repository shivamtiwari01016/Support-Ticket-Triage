"""Train, evaluate, and serialize the ticket category classifier."""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

from ticket_triage.data import CATEGORIES, load_ticket_data
from ticket_triage.model import build_classifier

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _git_sha() -> str:
    """Best-effort git commit hash for reproducible model tracking."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            check=True,
            text=True,
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _bootstrap_confidence_interval(
    values: list[float] | np.ndarray, confidence: float = 0.95
) -> tuple[float, float]:
    """Return percentile CI bounds for a scalar metric using a simple bootstrap."""
    if not values:
        return 0.0, 0.0
    rng = np.random.default_rng(42)
    sample = np.asarray(values, dtype=float)
    boot = np.empty(2000, dtype=float)
    for idx in range(boot.size):
        sample_idx = rng.choice(sample, size=len(sample), replace=True)
        boot[idx] = float(sample_idx.mean())
    alpha = 1.0 - confidence
    lower, upper = np.quantile(boot, [alpha / 2.0, 1.0 - alpha / 2.0])
    return float(lower), float(upper)


def _bootstrap_metric_confidence_interval(
    labels: list[str] | np.ndarray,
    predictions: list[str] | np.ndarray,
    metric_name: str,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Bootstrap a scalar metric over the held-out labels and predictions."""
    if len(labels) == 0 or len(predictions) == 0:
        return 0.0, 0.0
    rng = np.random.default_rng(42)
    alpha = 1.0 - confidence
    scores = []
    for _ in range(2000):
        indices = rng.integers(0, len(labels), size=len(labels))
        sample_labels = np.asarray(labels)[indices]
        sample_predictions = np.asarray(predictions)[indices]
        _, _, score, _ = precision_recall_fscore_support(
            sample_labels,
            sample_predictions,
            average=metric_name,
            zero_division=0,
        )
        scores.append(float(score))
    lower, upper = np.quantile(scores, [alpha / 2.0, 1.0 - alpha / 2.0])
    return float(lower), float(upper)


def train_and_evaluate(
    data_path: str | Path,
    model_path: str | Path,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict:
    """Fit on a stratified holdout split and save model plus evaluation metrics."""
    tickets = load_ticket_data(data_path)
    min_category_count = int(tickets["category"].value_counts().min())
    if min_category_count < 2:
        raise ValueError("Each category needs at least two rows for a stratified split.")

    n_splits = min(5, min_category_count)
    if n_splits < 2:
        raise ValueError("Need at least two rows per category for cross-validation.")

    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    classifier_template = build_classifier()
    cv_scores = cross_val_score(
        classifier_template,
        tickets["text"],
        tickets["category"],
        cv=cv,
        scoring="f1_macro",
        n_jobs=None,
    )

    train_text, test_text, train_labels, test_labels = train_test_split(
        tickets["text"],
        tickets["category"],
        test_size=test_size,
        random_state=random_state,
        stratify=tickets["category"],
    )

    classifier = build_classifier()
    classifier.fit(train_text, train_labels)
    predictions = classifier.predict(test_text)
    weighted_precision, weighted_recall, weighted_f1, _ = (
        precision_recall_fscore_support(
            test_labels, predictions, average="weighted", zero_division=0
        )
    )
    macro_precision, macro_recall, macro_f1, _ = precision_recall_fscore_support(
        test_labels, predictions, average="macro", zero_division=0
    )
    majority_baseline_accuracy = float(test_labels.value_counts(normalize=True).max())
    accuracy_value = float(accuracy_score(test_labels, predictions))
    accuracy_ci_lower, accuracy_ci_upper = _bootstrap_confidence_interval(
        [float(pred == truth) for pred, truth in zip(predictions, test_labels)]
    )
    macro_f1_ci_lower, macro_f1_ci_upper = _bootstrap_metric_confidence_interval(
        test_labels,
        predictions,
        metric_name="macro",
    )

    metrics = {
        "dataset_rows": int(len(tickets)),
        "train_rows": int(len(train_text)),
        "test_rows": int(len(test_text)),
        "random_state": random_state,
        "test_size": test_size,
        "n_cv_folds": int(n_splits),
        "cv_macro_f1_mean": float(np.mean(cv_scores)),
        "cv_macro_f1_std": float(np.std(cv_scores, ddof=0)),
        "cv_macro_f1_scores": [float(score) for score in cv_scores],
        "category_counts": {
            str(label): int(count)
            for label, count in tickets["category"].value_counts().items()
        },
        "accuracy": accuracy_value,
        "accuracy_ci95": [accuracy_ci_lower, accuracy_ci_upper],
        "weighted_precision": float(weighted_precision),
        "weighted_recall": float(weighted_recall),
        "weighted_f1": float(weighted_f1),
        "majority_baseline_accuracy": majority_baseline_accuracy,
        "macro_precision": float(macro_precision),
        "macro_recall": float(macro_recall),
        "macro_f1": float(macro_f1),
        "macro_f1_ci95": [macro_f1_ci_lower, macro_f1_ci_upper],
        "classification_report": classification_report(
            test_labels,
            predictions,
            labels=list(CATEGORIES),
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix": confusion_matrix(
            test_labels, predictions, labels=list(CATEGORIES)
        ).tolist(),
        "confusion_matrix_labels": list(CATEGORIES),
        "git_sha": _git_sha(),
        "python_version": sys.version.split()[0],
        "training_timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }

    destination = Path(model_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(classifier, destination)
    metrics_path = destination.with_name("evaluation.json")
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=PROJECT_ROOT / "dataset/customer_support_tickets.csv",
        help="Path to the support ticket CSV dataset",
    )
    parser.add_argument(
        "--model-out",
        type=Path,
        default=PROJECT_ROOT / "models/ticket_triage.joblib",
        help="Where to save the trained model",
    )
    args = parser.parse_args()

    metrics = train_and_evaluate(args.data, args.model_out)
    print(f"Saved model: {args.model_out}")
    print(f"Saved metrics: {args.model_out.with_name('evaluation.json')}")
    for metric in (
        "accuracy",
        "weighted_precision",
        "weighted_recall",
        "weighted_f1",
        "macro_f1",
        "majority_baseline_accuracy",
    ):
        print(f"{metric}: {metrics[metric]:.4f}")
    print(json.dumps(metrics["classification_report"], indent=2))


if __name__ == "__main__":
    main()
