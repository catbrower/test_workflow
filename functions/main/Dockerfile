FROM python:3.12-slim

# Common library (workflow.py, runner.py, etc.)
COPY common/src/ /app/

# Function package
COPY functions/main/pyproject.toml /function/
COPY functions/main/src/ /function/src/

WORKDIR /function

RUN pip install --no-cache-dir . && \
    PYTHONPATH=/app:/function/src python /app/compile_descriptor.py /app/descriptor.json

ENV PYTHONPATH=/app:/function/src
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "/app/runner.py"]
