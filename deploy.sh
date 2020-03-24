#!/bin/bash

if [ "$#" != "2" ]; then
  echo "Usage: $0 GCP_PROJECT LANGUAGE" 1>&2
  exit 1
fi

LANGUAGES="node python rust"

if ! grep -oh "$2" 2>&1 1>/dev/null <<< "${LANGUAGES}"; then
  echo "Unsupported language \"$2\"" 1>&2
  echo "Supported languages: ${LANGUAGES}" 1>&2
  exit 1
fi


GCP_PROJECT="$1"
LANGUAGE="$2"
CONTAINER_TAG="gcr.io/${GCP_PROJECT}/grpc-calculator:latest"

set -x
(cd "${LANGUAGE}"
  docker build -t "${CONTAINER_TAG}" .
  docker push "${CONTAINER_TAG}"
  gcloud run deploy --image "${CONTAINER_TAG}" --platform managed --project=${GCP_PROJECT}
)
