FROM rust@sha256:de00dbf06ed1a9426bd044f619e6f782e78b83bcfefb1570cfd342f84d6f424a AS builder

ARG VERS="3.11.4"
ARG ARCH="linux-x86_64"

RUN apt update && apt -y install wget unzip && \
    wget https://github.com/protocolbuffers/protobuf/releases/download/v${VERS}/protoc-${VERS}-${ARCH}.zip \
    --output-document=/protoc-${VERS}-${ARCH}.zip && \
    unzip -o protoc-${VERS}-${ARCH}.zip -d /protoc-${VERS}-${ARCH}

ENV PATH="${PATH}:/protoc-${VERS}-${ARCH}/bin"

WORKDIR /srv/grpc

# Thanks https://alexbrand.dev/post/how-to-package-rust-applications-into-minimal-docker-containers/
RUN rustup target add x86_64-unknown-linux-musl

COPY . .

# Build a static binary using musl libs
RUN cargo install --target x86_64-unknown-linux-musl --path .

FROM scratch AS runtime

COPY --from=builder /usr/local/cargo/bin/server .

ENTRYPOINT ["./server"]