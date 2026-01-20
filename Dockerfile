FROM python:3.11-slim

# Install system dependencies for libvirt
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libvirt-dev \
    libvirt0 \
    pkg-config \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
# Use --no-build-isolation to avoid build issues with libvirt-python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir prometheus-client==0.19.0 psutil==5.9.8 && \
    pip install --no-cache-dir --no-build-isolation libvirt-python

# Copy the exporter script
COPY insatomcat_exporter.py .
COPY ha_cluster_exporter .
COPY start.sh /
RUN chmod +x /start.sh ha_cluster_exporter insatomcat_exporter.py

# Expose the metrics port
EXPOSE 9184

# Run the exporter
CMD ["/start.sh"]
