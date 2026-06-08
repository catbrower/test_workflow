FROM python:3.12-slim

# Build context must be the swarmopt/ parent directory:
#   docker build -f test_workflow/functions/main/Dockerfile ..
ARG ARTIFACTORY_PIP_URL=https://artifactory.catbrower.com:9443/artifactory/api/pypi/pypi-virtual/simple

# Copy SDK source to /app/ for bare imports (models, workflow, decorators, etc.)
COPY swarm-sdk-python/src/ /app/

# Function package
COPY test_workflow/functions/main/pyproject.toml /function/
COPY test_workflow/functions/main/src/ /function/src/

WORKDIR /function

RUN pip install --no-cache-dir \
        --index-url ${ARTIFACTORY_PIP_URL} \
        --trusted-host artifactory.catbrower.com \
        redis pydantic kubernetes && \
    PYTHONPATH=/app:/function/src python /app/compile_descriptor.py /app/descriptor.json

ENV PYTHONPATH=/app:/function/src
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "/app/runner.py"]
