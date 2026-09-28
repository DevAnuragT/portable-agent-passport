FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY tests ./tests

ENV PYTHONPATH=/app/src
CMD ["python", "-m", "agent_passport", "verify"]
