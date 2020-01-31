#!/bin/bash

PROTO_CHECKSUMS=$(find . -name calculator.proto -exec md5sum {} \;)
UNIQUE_COUNT=$(echo "$PROTO_CHECKSUMS" | \
                 awk '{print $1;}' | \
                 sort | \
                 uniq | \
                 wc -l)

if [ "${UNIQUE_COUNT}" != "1" ]; then
  printf "Not all proto files are identical:\n%s\n" \
         "${PROTO_CHECKSUMS}" 1>&2
  exit 1
fi

exit 0
