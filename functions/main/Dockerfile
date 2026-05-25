FROM python:3.12-slim

# Common library (workflow.py, runner.py, etc.)
COPY common/src/ /app/

# Function package
COPY functions/main/pyproject.toml /function/
COPY functions/main/src/ /function/src/

WORKDIR /function

RUN pip install --no-cache-dir .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["run"]
