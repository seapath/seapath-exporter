FROM python:3.11-slim AS builder

# Build dependencies of libvirt-python, which ships as a source distribution.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libvirt-dev \
    pkg-config \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# --no-build-isolation avoids build issues with libvirt-python.
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel && \
    /opt/venv/bin/pip install --no-cache-dir --no-build-isolation -r requirements.txt


FROM python:3.11-slim

# Only the libvirt shared library is needed at runtime, the toolchain stays in
# the builder stage.
RUN apt-get update && \
    apt-get install -y --no-install-recommends libvirt0 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /app
COPY insatomcat_exporter.py .

EXPOSE 9184

# Exec form so that the exporter runs as PID 1 and gets the SIGTERM sent by
# podman stop, instead of being killed after the stop timeout.
CMD ["python", "/app/insatomcat_exporter.py"]
