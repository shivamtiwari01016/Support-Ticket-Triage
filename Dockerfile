FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt

COPY . .

RUN python -m spacy download en_core_web_sm

EXPOSE 8000

CMD ["uvicorn", "ticket_triage.api:app", "--host", "0.0.0.0", "--port", "8000"]
