# Build from test_workflow/functions/hello/ (or any directory containing src/):
#   docker build -t workflow-hello:local test_workflow/functions/hello
#
# Load into cluster:
#   minikube image load workflow-hello:local

FROM python:3.12-slim

RUN pip install --no-cache-dir redis

COPY src/hello.py /app/hello.py

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "/app/hello.py"]
