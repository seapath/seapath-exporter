#!/bin/bash

# Step 1: Build the Podman image
DOCKER_USERNAME="insatomcat"
IMAGE_NAME="insatomcat-exporter"
VERSION="0.0.1"

echo "Building Podman image..."
podman build -t ${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION} .
podman tag ${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION} ${DOCKER_USERNAME}/${IMAGE_NAME}:latest

# Step 2: Test the image locally (optional)
echo "Testing the image locally..."
# Note: Podman runs rootless by default, adjust volumes as needed
podman run -d \
  --name insatomcat-exporter-test \
  -p 9184:9184 \
  -v /var/run/libvirt/libvirt-sock:/var/run/libvirt/libvirt-sock:ro \
  -v /var/run/libvirt/qemu:/var/run/libvirt/qemu:ro \
  --pid=host \
  ${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}

echo "Waiting for exporter to start..."
sleep 5

echo "Testing metrics endpoint..."
curl http://localhost:9184/metrics

echo "Stopping test container..."
podman stop insatomcat-exporter-test
podman rm insatomcat-exporter-test

# Step 3: Login to Docker Hub
echo "Logging in to Docker Hub..."
podman login docker.io

# Step 4: Push the image to Docker Hub
echo "Pushing image to Docker Hub..."
podman push ${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}
podman push ${DOCKER_USERNAME}/${IMAGE_NAME}:latest

echo "Done! Your image is available at:"
echo "podman pull docker.io/${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}"
echo "podman pull docker.io/${DOCKER_USERNAME}/${IMAGE_NAME}:latest"
