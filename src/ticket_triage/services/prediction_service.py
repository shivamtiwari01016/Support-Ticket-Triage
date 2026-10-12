"""Inference, urgency scoring, routing, and persistence workflow."""

from sqlalchemy.orm import Session

from ticket_triage.repositories.ticket_repository import TicketRepository
from ticket_triage.services.routing_service import assign_team
from ticket_triage.urgency import score_urgency


class PredictionService:
    def __init__(self, classifier, model_version: str):
        self.classifier = classifier
        self.model_version = model_version

    def explain_prediction(self, text: str) -> dict[str, object]:
        if not hasattr(self.classifier, "predict_proba"):
            prediction = str(self.classifier.predict([text])[0])
            return {
                "confidence": 1.0,
                "top_terms": [],
                "per_class": {prediction: 1.0},
            }

        probabilities = self.classifier.predict_proba([text])[0]
        labels = list(self.classifier.classes_)
        predicted_index = int(probabilities.argmax())
        confidence = float(probabilities[predicted_index])
        explanation = {"confidence": confidence, "per_class": {label: float(prob) for label, prob in zip(labels, probabilities)}}

        pipeline = getattr(self.classifier, "named_steps", None)
        if pipeline is not None:
            vectorizer = pipeline.get("tfidf")
            estimator = pipeline.get("classifier")
            if vectorizer is not None and estimator is not None and hasattr(estimator, "coef_"):
                feature_names = vectorizer.get_feature_names_out()
                coef = estimator.coef_[predicted_index]
                ranked = sorted(
                    zip(feature_names, coef),
                    key=lambda item: abs(item[1]),
                    reverse=True,
                )[:10]
                explanation["top_terms"] = [token for token, _ in ranked if token]
        else:
            explanation["top_terms"] = []
        return explanation

    def predict_and_persist(self, session: Session, text: str):
        category = str(self.classifier.predict([text])[0])
        urgency = score_urgency(text)
        team = assign_team(category)
        return TicketRepository(session).create_with_prediction(
            text=text,
            category=category,
            assigned_team=team,
            urgency_score=float(urgency["score"]) / 100,
            urgency_level=str(urgency["level"]),
            model_version=self.model_version,
        )
