FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ARG INSTALL_ML=0
COPY requirements.txt requirements-ml.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    if [ "$INSTALL_ML" = "1" ]; then pip install --no-cache-dir -r requirements-ml.txt; fi
COPY . .
ENV ML_ENABLED=0
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}
