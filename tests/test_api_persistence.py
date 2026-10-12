import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ticket_triage import api as api_module
from ticket_triage.api import create_app
from ticket_triage.models import Base
from ticket_triage.repositories.ticket_repository import TicketRepository
from ticket_triage.services import prediction_service as prediction_service_module


class FakeClassifier:
    def predict(self, texts):
        return ["Billing" for _ in texts]


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    evaluation_path = tmp_path / "evaluation.json"
    evaluation_path.write_text(
        json.dumps(
            {
                "accuracy": 0.25,
                "weighted_precision": 0.3,
                "weighted_recall": 0.25,
                "weighted_f1": 0.26,
                "macro_precision": 0.24,
                "macro_recall": 0.25,
                "macro_f1": 0.24,
                "majority_baseline_accuracy": 0.4,
                "dataset_rows": 100,
                "test_rows": 20,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        prediction_service_module,
        "score_urgency",
        lambda text: {"score": 84, "level": "High", "sentiment_compound": -0.68},
    )
    monkeypatch.setattr(api_module, "API_KEY", "test-key")
    monkeypatch.setattr(api_module, "ensure_nlp_ready", lambda: None)
    monkeypatch.setattr(api_module, "ensure_urgency_ready", lambda: None)
    app = create_app(
        model_path=tmp_path / "unused-model.joblib",
        evaluation_path=evaluation_path,
        database_url=None,
        classifier=FakeClassifier(),
        session_factory=factory,
    )
    with TestClient(app, headers={"X-API-Key": "test-key"}) as test_client:
        yield test_client
    engine.dispose()


def test_health_reports_database_and_model(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert response.json() == {
        "status": "ok",
        "database": "connected",
        "model": "loaded",
        "nlp": "ready",
    }


def test_missing_or_wrong_api_key_is_rejected(monkeypatch, tmp_path):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(api_module, "API_KEY", "test-key")
    app = create_app(
        model_path=tmp_path / "unused-model.joblib",
        evaluation_path=tmp_path / "evaluation.json",
        database_url=None,
        classifier=FakeClassifier(),
        session_factory=factory,
    )

    with TestClient(app) as no_key:
        assert no_key.get("/api/v1/tickets").status_code == 401

    with TestClient(app, headers={"X-API-Key": "wrong-key"}) as wrong_key:
        assert wrong_key.get("/api/v1/tickets").status_code == 401

    with TestClient(app, headers={"X-API-Key": "test-key"}) as good_key:
        assert good_key.get("/api/v1/health").status_code == 200

    engine.dispose()


def test_predict_persists_ticket_and_returns_public_record(client):
    response = client.post("/predict", json={"text": "  My payment was deducted twice.  "})

    assert response.status_code == 200
    body = response.json()
    assert body["ticket_id"].startswith("TKT-")
    assert body["text"] == "My payment was deducted twice."
    assert body["category"] == "Billing"
    assert body["assigned_team"] == "Billing Team"
    assert body["status"] == "open"
    assert body["urgency"] == 0.84
    assert body["urgency_level"] == "High"
    assert body["created_at"]
    assert body["confidence"] is not None
    assert body["explanation"]["per_class"]["Billing"] >= 0
    assert "id" not in body

    assert client.get("/tickets").json() == [body]
    assert client.get(f"/tickets/{body['ticket_id']}").json() == body


def test_ticket_validation_lookup_statistics_and_metrics(client):
    assert client.post("/predict", json={"text": " \n "}).status_code == 422
    assert client.get("/tickets?limit=101").status_code == 422
    assert client.get("/tickets/unknown-id").status_code == 404

    empty_statistics = client.get("/statistics").json()
    assert empty_statistics == {
        "total_tickets": 0,
        "average_urgency": 0.0,
        "category_distribution": {},
    }

    metrics = client.get("/metrics").json()
    assert metrics["accuracy"] == 0.25
    assert metrics["precision"] == 0.3
    assert metrics["majority_baseline_accuracy"] == 0.4


def test_versioned_routes_are_documented_and_legacy_predict_remains_available(client):
    versioned = client.post("/api/v1/predictions", json={"text": "Billing question"})
    legacy = client.post("/predict", json={"text": "Another billing question"})
    paths = client.get("/openapi.json").json()["paths"]

    assert versioned.status_code == 200
    assert versioned.json()["assigned_team"] == "Billing Team"
    assert legacy.status_code == 200
    assert "/api/v1/predictions" in paths
    assert "/predict" not in paths


def test_prediction_updates_database_statistics_and_history_limit(client):
    first = client.post("/predict", json={"text": "Payment question"}).json()
    second = client.post("/predict", json={"text": "Refund question"}).json()

    statistics = client.get("/statistics").json()
    recent = client.get("/tickets?limit=1").json()

    assert statistics == {
        "total_tickets": 2,
        "average_urgency": 0.84,
        "category_distribution": {"Billing": 2},
    }
    assert len(recent) == 1
    assert recent[0]["ticket_id"] == second["ticket_id"]
    assert first["ticket_id"] != second["ticket_id"]


def test_persistence_failure_returns_safe_service_error(client, monkeypatch, caplog):
    def fail_save(*args, **kwargs):
        raise SQLAlchemyError("private connection details")

    monkeypatch.setattr(TicketRepository, "create_with_prediction", fail_save)
    response = client.post("/predict", json={"text": "Refund question"})

    assert response.status_code == 503
    assert response.json()["detail"] == "The prediction could not be saved. Please retry the request."
    assert "private connection details" not in response.text
    assert "private connection details" not in caplog.text


def test_read_database_failure_uses_safe_consistent_error(client, monkeypatch):
    def fail_list(*args, **kwargs):
        raise SQLAlchemyError("private select details")

    monkeypatch.setattr(TicketRepository, "list_recent", fail_list)
    response = client.get("/api/v1/tickets")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "The database service is unavailable. Please try again shortly."
    }
    assert "private select details" not in response.text


def test_health_marks_database_unavailable(client, monkeypatch):
    def fail_health(engine):
        raise SQLAlchemyError("private connection details")

    monkeypatch.setattr(api_module, "verify_database", fail_health)
    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["detail"]["database"] == "unavailable"


def test_ticket_status_can_be_updated(client):
    created = client.post("/predict", json={"text": "Billing refund question"}).json()

    updated = client.patch(
        f"/api/v1/tickets/{created['ticket_id']}",
        json={"status": "in_progress"},
    )

    assert updated.status_code == 200
    assert updated.json()["status"] == "in_progress"
    assert client.get(f"/tickets/{created['ticket_id']}").json()["status"] == "in_progress"


def test_prediction_requests_are_guarded_by_size_and_rate_limits(client, monkeypatch):
    monkeypatch.setattr(api_module, "MAX_REQUEST_BYTES", 20)
    monkeypatch.setattr(api_module, "RATE_LIMIT_PER_MINUTE", 1)
    api_module.RATE_LIMIT_STATE.clear()

    oversized = client.post("/predict", json={"text": "x" * 100})
    assert oversized.status_code == 413

    monkeypatch.setattr(api_module, "MAX_REQUEST_BYTES", 1024 * 1024)
    first = client.post("/predict", json={"text": "few words"})
    second = client.post("/predict", json={"text": "another request"})

    assert first.status_code == 200
    assert second.status_code == 429


def test_startup_fails_clearly_without_mysql_configuration(monkeypatch):
    monkeypatch.setattr(api_module, "ensure_nlp_ready", lambda: None)
    monkeypatch.setattr(api_module, "ensure_urgency_ready", lambda: None)
    app = create_app(database_url=None, classifier=FakeClassifier())

    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        with TestClient(app):
            pass


def test_startup_fails_clearly_when_spacy_model_is_unavailable(monkeypatch):
    def fail_nlp_load():
        raise RuntimeError("missing configured spaCy model")

    monkeypatch.setattr(api_module, "ensure_nlp_ready", fail_nlp_load)
    monkeypatch.setattr(api_module, "ensure_urgency_ready", lambda: None)
    app = create_app(database_url=None, classifier=FakeClassifier())

    with pytest.raises(RuntimeError, match="Required NLP resources"):
        with TestClient(app):
            pass


def test_startup_fails_clearly_when_sentiment_resources_are_unavailable(monkeypatch):
    monkeypatch.setattr(api_module, "ensure_nlp_ready", lambda: None)

    def fail_sentiment_load():
        raise RuntimeError("missing VADER lexicon")

    monkeypatch.setattr(api_module, "ensure_urgency_ready", fail_sentiment_load)
    app = create_app(database_url=None, classifier=FakeClassifier())

    with pytest.raises(RuntimeError, match="Required NLP resources"):
        with TestClient(app):
            pass
