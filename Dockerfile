FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /opt/service

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip

FROM base AS poller-runtime

COPY poller/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY poller/app ./app
COPY poller/run.py ./run.py

RUN mkdir -p /opt/service/var/state

CMD ["python", "run.py"]

FROM base AS orchestrator-runtime

COPY orchestrator/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY orchestrator/app ./app
COPY orchestrator/run.py ./run.py

CMD ["python", "run.py"]

FROM base AS game-runtime

COPY game/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY game/alembic.ini game/run.py ./
COPY game/alembic ./alembic
COPY game/app ./app

EXPOSE 8001

CMD ["python", "run.py"]
