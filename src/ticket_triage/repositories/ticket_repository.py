"""SQLAlchemy persistence operations for tickets and prediction history."""

from decimal import Decimal
from secrets import token_hex

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from ticket_triage.models import Prediction, Ticket


def generate_ticket_id() -> str:
    return f"TKT-{token_hex(6).upper()}"


class TicketRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_with_prediction(
        self,
        *,
        text: str,
        category: str,
        assigned_team: str,
        urgency_score: float,
        urgency_level: str,
        model_version: str,
    ) -> Ticket:
        """Commit ticket and prediction together, rolling both back on failure."""
        ticket = Ticket(ticket_id=generate_ticket_id(), text=text, status="open")
        ticket.predictions.append(
            Prediction(
                category=category,
                assigned_team=assigned_team,
                urgency_score=Decimal(str(round(urgency_score, 4))),
                urgency_level=urgency_level,
                model_version=model_version,
            )
        )
        self.session.add(ticket)

        try:
            self.session.flush()
            self.session.refresh(ticket)
            self.session.commit()
            return ticket
        except SQLAlchemyError:
            self.session.rollback()
            raise

    def list_recent(self, limit: int) -> list[Ticket]:
        statement = (
            select(Ticket)
            .options(selectinload(Ticket.predictions))
            .order_by(Ticket.created_at.desc(), Ticket.id.desc())
            .limit(limit)
        )
        return list(self.session.scalars(statement).all())

    def get_by_ticket_id(self, ticket_id: str) -> Ticket | None:
        statement = (
            select(Ticket)
            .options(selectinload(Ticket.predictions))
            .where(Ticket.ticket_id == ticket_id)
        )
        return self.session.scalar(statement)

    def update_status(self, ticket_id: str, status: str) -> Ticket | None:
        ticket = self.get_by_ticket_id(ticket_id)
        if ticket is None:
            return None
        ticket.status = status
        try:
            self.session.add(ticket)
            self.session.commit()
            self.session.refresh(ticket)
            return ticket
        except SQLAlchemyError:
            self.session.rollback()
            raise

    def statistics(self) -> dict:
        total_tickets = self.session.scalar(select(func.count(Ticket.id))) or 0
        average_urgency = self.session.scalar(select(func.avg(Prediction.urgency_score)))
        category_counts = self.session.execute(
            select(Prediction.category, func.count(Prediction.id)).group_by(
                Prediction.category
            )
        ).all()
        return {
            "total_tickets": int(total_tickets),
            "average_urgency": (
                round(float(average_urgency), 4) if average_urgency is not None else 0.0
            ),
            "category_distribution": {
                category: int(count) for category, count in category_counts
            },
        }
