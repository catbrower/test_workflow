FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/catbrower/client.git /tmp/client \
    && pip3 install --no-cache-dir /tmp/client \
    && rm -rf /tmp/client
WORKDIR /app
COPY . .
RUN pip3 install --no-cache-dir pydantic pyyaml redis
ENTRYPOINT ["python3", "runner.py"]
