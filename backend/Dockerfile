FROM python:3.11-slim

ENV PYTHONBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]