# Service IA FastAPI (AS-S1-005). Execute en utilisateur non privilegie.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt presidio-analyzer presidio-anonymizer spacy
RUN pip install --no-cache-dir lingua-language-detector==2.2.0
RUN python -m spacy download en_core_web_lg
RUN python -m spacy download fr_core_news_md

RUN pip install --no-cache-dir pypdf==6.1.3

# `app` importe `evaluation.results` : les deux paquets sont necessaires.
COPY app ./app
COPY evaluation ./evaluation
COPY config ./config

RUN useradd --system --create-home --home-dir /home/appuser appuser
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
