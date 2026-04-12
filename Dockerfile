FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/appuser \
    PATH=/home/appuser/.local/bin:$PATH

RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser
USER appuser
WORKDIR $HOME/app

RUN python -m pip install --upgrade pip setuptools wheel

COPY --chown=appuser requirements.txt .
RUN pip install -r requirements.txt

RUN mkdir -p artifacts/runs artifacts/logs

COPY --chown=appuser . .

EXPOSE 7860
CMD ["python", "app.py"]
