# Vision sidecar — Phase 1 stub.
# Bazel does not own this build because rules_python is not wired in
# MODULE.bazel; the SPA follows the same "build out-of-band, Bazel
# packages the output" pattern. If rules_python is added later, this
# Dockerfile can be replaced by a py_oci_image target.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# opencv-python-headless still needs libgl-shim and libglib for its
# shared objects to load even though no display is attached.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgl1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY sidecar.py ./
COPY schemas ./schemas

USER nobody
EXPOSE 9100
ENTRYPOINT ["python", "/app/sidecar.py"]
