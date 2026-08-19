FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels ".[video]"


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/*.whl \
    && rm -rf /wheels

RUN mkdir -p /output

ENTRYPOINT ["stoatswarm-tunnel"]
CMD ["--seed", "12345", "--cells", "30", "--video", "/output/tunnel.mp4"]
