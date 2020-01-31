#!/bin/bash

if [ "$#" != "1" ]; then
    echo "Usage: $0 GCP_PROJECT" >/dev/stderr
    exit 1
fi

GCP_PROJECT="$1"
CONTAINER_TAG="gcr.io/${GCP_PROJECT}/grpc-calculator:latest"

set -x

docker build -t "${CONTAINER_TAG}" .
docker push "${CONTAINER_TAG}"
gcloud run deploy --image "${CONTAINER_TAG}" --platform managed
