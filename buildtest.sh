#!/bin/bash
# Build the image and check that the metrics endpoint answers. Publishing is
# done by the "Container image" workflow when a version tag is pushed.
set -euo pipefail

IMAGE="seapath-exporter:test"
CONTAINER="seapath-exporter-test"

echo "Building the image..."
podman build -t "${IMAGE}" .

echo "Testing the image locally..."
# Note: Podman runs rootless by default, adjust volumes as needed
podman run -d \
  --name "${CONTAINER}" \
  -p 9184:9184 \
  -v /var/run/libvirt/libvirt-sock:/var/run/libvirt/libvirt-sock:ro \
  -v /var/run/libvirt/qemu:/var/run/libvirt/qemu:ro \
  --pid=host \
  "${IMAGE}"
trap 'podman rm -f "${CONTAINER}" >/dev/null' EXIT

echo "Waiting for exporter to start..."
sleep 5

echo "Testing metrics endpoint..."
curl --fail http://localhost:9184/metrics
