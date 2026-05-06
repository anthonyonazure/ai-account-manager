# AAM bot endpoint — production container.
# Built for Azure Container Apps; runs the FastAPI /api/messages endpoint
# (aam.teams_bot_server) on $PORT. The Bot Framework adapter speaks to it
# directly over HTTPS via Container Apps' built-in ingress + TLS.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Build deps that some wheels still compile from source on slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential \
    && rm -rf /var/lib/apt/lists/*

# Toolkit dep is cloned at build time so we don't depend on a PyPI release.
ARG TOOLKIT_REF=main
RUN git clone --depth 1 --branch ${TOOLKIT_REF} \
    https://github.com/anthonyonazure/b2b-agent-toolkit.git /toolkit

# Install toolkit + AAM
COPY pyproject.toml README.md ./
COPY src ./src
COPY mock_portal ./mock_portal

RUN pip install --upgrade pip \
    && pip install /toolkit \
    && pip install .

# Container Apps assigns $PORT (default 8080); we listen on it.
ENV PORT=8080
EXPOSE 8080

# Health + Bot Framework messaging endpoint live in the same FastAPI app.
CMD ["sh", "-c", "uvicorn aam.teams_bot_server:app --host 0.0.0.0 --port ${PORT}"]
