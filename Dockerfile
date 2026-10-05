FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY app ./app
COPY dbt ./dbt
COPY dags ./dags
COPY scripts ./scripts
COPY config ./config
COPY docs ./docs
COPY .streamlit ./.streamlit

RUN pip install --no-cache-dir -e ".[dev]"

RUN mkdir -p /app/dagster_home /app/models

CMD ["bash"]