# PlatePlayed runtime image.
# Includes ffmpeg for robust stream decoding. Install ML extras at build time
# by uncommenting the requirements-ml.txt line below.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-ml.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# Uncomment to bake in the real ALPR engine (large download):
# RUN pip install --no-cache-dir -r requirements-ml.txt

COPY . .
RUN pip install --no-cache-dir -e .

# Dashboard / API
EXPOSE 8000

# Default: run the watcher. Override with `serve` for the dashboard.
ENTRYPOINT ["plateplayed"]
CMD ["run", "-c", "config.yaml"]
