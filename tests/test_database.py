import sqlite3
from decimal import Decimal

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ticket_triage.database import (
    create_database_engine,
    upgrade_schema,
    verify_database,
    verify_schema,
)
from ticket_triage.models import Base, Prediction, Ticket
from ticket_triage.repositories.ticket_repository import TicketRepository


@pytest.fixture
def database():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield engine, session
    engine.dispose()


def test_database_connection_and_mysql_runtime_url():
    engine = create_database_engine(
        "mysql+pymysql://user:secret@127.0.0.1:3306/support_ticket_triage"
    )
    try:
        assert engine.dialect.name == "mysql"
    finally:
        engine.dispose()

    with pytest.raises(ValueError, match=r"mysql\+pymysql"):
        create_database_engine("sqlite+pysqlite:///:memory:")


def test_initial_alembic_migration_creates_expected_tables(tmp_path):
    database_path = tmp_path / "migration-test.db"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"

    upgrade_schema(database_url)

    engine = create_engine(database_url)
    try:
        verify_schema(engine)
        inspector = inspect(engine)
        assert {"tickets", "predictions", "alembic_version"}.issubset(
            inspector.get_table_names()
        )
        ticket_columns = {column["name"] for column in inspector.get_columns("tickets")}
        prediction_columns = {
            column["name"] for column in inspector.get_columns("predictions")
        }
        assert {"id", "ticket_id", "text", "status", "created_at", "updated_at"} <= ticket_columns
        assert {"ticket_db_id", "assigned_team", "model_version"} <= prediction_columns
        with engine.connect() as connection:
            differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        assert differences == []
        with engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = 'stale'"))
        with pytest.raises(RuntimeError, match="revision is not current"):
            verify_schema(engine)
    finally:
        engine.dispose()


def test_verify_schema_skips_migration_history_when_migrations_directory_is_missing(monkeypatch, tmp_path):
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    monkeypatch.setattr("ticket_triage.database.PROJECT_ROOT", tmp_path)

    try:
        verify_schema(engine, require_migration_history=True)
    finally:
        engine.dispose()


def test_ticket_prediction_relationship_and_retrieval(database):
    engine, session = database
    verify_database(engine)

    repository = TicketRepository(session)
    ticket = repository.create_with_prediction(
        text="Payment was deducted twice.",
        category="Billing",
        assigned_team="Billing Team",
        urgency_score=0.84,
        urgency_level="High",
        model_version="v1",
    )

    assert ticket.id is not None
    assert ticket.ticket_id.startswith("TKT-")
    assert ticket.predictions[0].ticket_db_id == ticket.id
    assert ticket.predictions[0].ticket is ticket
    assert ticket.predictions[0].urgency_score == Decimal("0.8400")
    assert repository.get_by_ticket_id(ticket.ticket_id).text == ticket.text
    assert len(repository.list_recent(limit=1)) == 1


def test_statistics_aggregate_persisted_rows(database):
    _, session = database
    repository = TicketRepository(session)
    repository.create_with_prediction(
        text="Payment issue",
        category="Billing",
        assigned_team="Billing Team",
        urgency_score=0.8,
        urgency_level="High",
        model_version="v1",
    )
    repository.create_with_prediction(
        text="Account question",
        category="Account",
        assigned_team="Account Support",
        urgency_score=0.4,
        urgency_level="Medium",
        model_version="v1",
    )

    statistics = repository.statistics()

    assert statistics["total_tickets"] == 2
    assert statistics["average_urgency"] == 0.6
    assert statistics["category_distribution"] == {"Account": 1, "Billing": 1}


def test_prediction_failure_rolls_back_ticket_insert(database):
    engine, session = database

    def fail_prediction_insert(connection, cursor, statement, parameters, context, executemany):
        if statement.lower().startswith("insert into predictions"):
            raise sqlite3.IntegrityError("injected prediction insert failure")

    event.listen(engine, "before_cursor_execute", fail_prediction_insert)
    try:
        with pytest.raises(IntegrityError):
            TicketRepository(session).create_with_prediction(
                text="This should not be persisted.",
                category="General",
                assigned_team="Customer Support",
                urgency_score=0.5,
                urgency_level="Medium",
                model_version="v1",
            )
    finally:
        event.remove(engine, "before_cursor_execute", fail_prediction_insert)

    assert session.scalar(select(Ticket.id)) is None
    assert session.scalar(select(Prediction.id)) is None
