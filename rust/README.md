# gRPC in Google Cloud Run

*Estimated Reading Time: 20 minutes*

Google Cloud Run makes it easy to deploy and run REST servers, but it also
supports gRPC servers out of the box. This article will show you how to
deploy a gRPC service written in Rust to Cloud Run. For the full code, [check
out the Github repo.](https://github.com/grpc-ecosystem/grpc-cloud-run-example)

We'll be writing a simple remote calculator service. For the moment, it will
just support adding and subtracting floating point numbers, but once this is up
and running, you could easily extend it to add other features.

## The Protocol Buffer Definition

Take a look in [`calculator.proto`](calculator.proto) to see the full protocol buffer definition. If
you're not familiar with protocol buffers,
[take a moment to get acquainted.](https://developers.google.com/protocol-buffers)

```protobuf
enum Operation {
  ADD = 0;
  SUBTRACT = 1;
}

message BinaryOperation {
  float first_operand = 1;
  float second_operand = 2;
  Operation operation = 3;
};

message CalculationResult {
  float result = 1;
};

service Calculator {
  rpc Calculate (BinaryOperation) returns (CalculationResult);
};
```

Our service will be a simple unary RPC. We'll take two floats and one of two
operations. Then, we'll return the result of that operation.

## The Server

Let's start with the server.

Here's the `Cargo.toml` file:

```TOML
[package]
name = "grpc-cloud-run-example-rust"
version = "0.0.1"
edition = "2018"

[[bin]]
name = "server"
path = "src/main.rs"

[build-dependencies]
protoc-rust-grpc = "0.6.1"

[dependencies]
blake2 = "0.8.1"
futures = "0.3.4"
futures-cpupool = "0.1.8"
grpc = "0.6.2"
hex = "0.4.2"
protobuf = "2.8.2"
```

Two things to note about this:

1. `cargo` will build a binary called `server`
2. The build dependency (`protoc-rust-grpc`) compiles the protobuf automatically; the build dependency is itself dependent on 'protoc' being available in the path

Take a look at [`main.rs`](main.rs).

We define a struct type `CalculatorImpl` and implement the `Calculator` trait
that's required by the code generated from the protobuf file. This requires a
single function, `calculator`:

```rust
pub struct CalculatorImpl;
impl Calculator for CalculatorImpl {
    fn calculate(
        &self,
        _: RequestOptions,
        rqst: BinaryOperation,
    ) -> SingleResponse<CalculationResult> {
        let op1: f32 = rqst.get_first_operand();
        let op2: f32 = rqst.get_second_operand();
        let result: f32 = match rqst.get_operation() {
            Operation::ADD => op1 + op2,
            Operation::SUBTRACT => op1 - op2,
        };
        let resp = CalculationResult {
            result: result,
            ..Default::default()
        };
        return SingleResponse::completed(resp);
    }
}
```

The `main` function is straightforward. 
Google Cloud Run will set up an environment variable called `PORT` on which your
server should listen. The first thing we do is pull that from the environment:

```rust
let key = "PORT";
let port = match env::var_os(key) {
    Some(val) => match val.to_str() {
        Some(s) => match s.parse::<u16>() {
            Ok(p) => p,
            Err(e) => return Err(e),
        },
        None => 50051,
    },
    None => 50051,
};
```
> **NB** This code is longer than the gRPC server!

Next, we set up a server bound to that port, listening on all interfaces.

```rust
let mut server = ServerBuilder::new_plain();
server.http.set_port(port);
server.add_service(CalculatorServer::new_service_def(CalculatorImpl));
let _server = server.build().expect("server");

println!("Starting: gRPC Listener [{}]", port);

loop {
    thread::park();
}```

Notice that we're not using TLS. Google Cloud Run's proxy
provides us with a TLS-encrypted proxy that handles the messy business of
setting up certs for us. The traffic from the proxy to the container with our
gRPC server in it goes through an encrypted tunnel, so we don't need to worry
about handling it ourselves. Cloud Run natively handles HTTP/2, so gRPC's
transport is well-supported.

## Connecting

Now let's test the server out locally. First, we install dependencies.

```bash
# The current version is 3.11.4
VERS="3.11.4"
# This value is for Linux x84-64
ARCH="linux-x86_64"
wget https://github.com/protocolbuffers/protobuf/releases/download/v${VERS}/protoc-${VERS}-${ARCH}.zip \
--output-document=./protoc-${VERS}-${ARCH}.zip

unzip -o protoc-${VERS}-${ARCH}.zip -d protoc-${VERS}-${ARCH}
```

Add `protoc` to the path:

```bash
PATH=${PATH}:${PWD}/protoc-${VERS}-${ARCH}/bin
```

The project includes a `build.rs` that generates the rust code from the `calculator.proto` file.
This is how we get the definitions for our `calculator.rs` and `calculator_grpc.rs`.

```rust
fn main() {
    protoc_rust_grpc::run(protoc_rust_grpc::Args {
        out_dir: "src/protos",
        includes: &["./"],
        input: &["protos/calculator.proto"],
        rust_protobuf: true, // also generate protobuf messages, not just services
        ..Default::default()
    })
    .expect("protoc-rust-grpc");
}
```

Finally, we start the server:

```bash
export PORT=50051
cargo run
```

Now the server should be listening on port `50051`. We'll use the tool
[`grpcurl`](https://github.com/fullstorydev/grpcurl) to manually interact with it.
On Linux and Mac you can install it with `curl -s https://grpc.io/get_grpcurl | bash`.

```bash
grpcurl \
  -plaintext \
  -proto protos/calculator.proto \
  -d '{"first_operand": 2.0, "second_operand": 3.0, "operation": "ADD"}' \
  localhost:50051 \
  Calculator.Calculate
```

We tell `grpcurl` where to find the protocol buffer definitions and server.
Then, we supply the request. `grpcurl` gives us a nice mapping from JSON to
protobuf. We can even supply the operation enumeration as a string. Finally, we
invoke the `Calculate` method on the `Calculator` service. If all goes well, you
should see:

```bash
{
  "result": 5
}
```

Great! We've got a working calculator server. Next, let's put it inside a
Docker container.

## Containerizing the Server

We're going to use the official Dockerhub rust [slim-buster](https://hub.docker.com/layers/rust/library/rust/slim-buster/images/sha256-de00dbf06ed1a9426bd044f619e6f782e78b83bcfefb1570cfd342f84d6f424a?context=explore) image as our base image.


```Dockerfile
FROM rust@sha256:de00dbf06ed1a9426bd044f619e6f782e78b83bcfefb1570cfd342f84d6f424a AS builder

ARG VERS="3.11.4"
ARG ARCH="linux-x86_64"

RUN apt update && apt -y install wget && \
    wget https://github.com/protocolbuffers/protobuf/releases/download/v${VERS}/protoc-${VERS}-${ARCH}.zip \
    --output-document=/protoc-${VERS}-${ARCH}.zip && \
    apt update && apt install -y unzip && \
    unzip -o protoc-${VERS}-${ARCH}.zip -d /protoc-${VERS}-${ARCH}
ENV PATH="${PATH}:/protoc/bin"

WORKDIR /srv/grpc

RUN rustup target add x86_64-unknown-linux-musl

COPY . .

RUN cargo install --target x86_64-unknown-linux-musl --path .
```

> **NB** Thanks to [alexbrand](https://alexbrand.dev/post/how-to-package-rust-applications-into-minimal-docker-containers/) for guidance building static binaries in Rust

Finally, we move the binary into a runtime container:

```Dockerfile
FROM scratch AS runtime

COPY --from=builder /usr/local/cargo/bin/server .
```

And set the container to run the server by default.

```Dockerfile
ENTRYPOINT ["./server"]
```

Now we can build our image. In order to deploy to Cloud Run, we'll be pushing to
the `gcr.io` container registry, so we'll tag it accordingly.

```bash
GCP_PROJECT=<Your GCP Project Name>

cargo clean # Remove ./target
docker build \
  --tag=gcr.io/${GCP_PROJECT}/grpc-calculator:latest \
  --file=./Dockerfile \
  .
```

> **NB** Don't forget that final `.`, it's critical.

The tag above will change based on your GCP project name. We're calling the
service `grpc-calculator` and using the `latest` tag.

Now, before we deploy to Cloud Run, let's make sure that we've containerized our
application properly. We'll test it by spinning up a local container.

```bash
PORT="50051" # Cloud Run will use `8080`
docker run \
  --interactive --tty \
  --publish=50051:${PORT} \
  --env=PORT=${PORT} \
  gcr.io/${GCP_PROJECT}/grpc-calculator:latest
```

If all goes well, `grpcurl` will give us the same result as before:

```bash
grpcurl \
    --plaintext \
    -proto calculator.proto \
    -d '{"first_operand": 2.0, "second_operand": 3.0, "operation": "ADD"}' \
    localhost:50051 \
    Calculator.Calculate
```

## Deploying to Cloud Run

Cloud Run needs to pull our application from a container registry, so the first
step is to push the image we just built.

Make sure that [you can use `gcloud`](https://cloud.google.com/sdk/gcloud/reference/auth/login)
and are [able to push to `gcr.io`.](https://cloud.google.com/container-registry/docs/pushing-and-pulling)

```bash
gcloud auth login
gcloud auth configure-docker
```

Now we can push our image.

```bash
docker push gcr.io/$GCP_PROJECT/grpc-calculator:latest
```

Finally, we deploy our application to Cloud Run:

```bash
GCP_REGION="us-west1" # Or ...
gcloud run deploy grpc-calculator \
--image=gcr.io/$GCP_PROJECT/grpc-calculator:latest \
--platform=managed \
--allow-unauthenticated \
--project=${GCP_PROJECT} \
--region=${GCP_REGION}
```

This command will give you a message like
```
Service [grpc-calculator] revision [grpc-calculator-00001-baw] has been deployed and is serving 100 percent of traffic at https://grpc-calculator-xyspwhk3xq-uc.a.run.app
```

We can programmatically determine the gRPC service's endpoint:

```bash
ENDPOINT=$(\
  gcloud run services list \
  --project=${GCP_PROJECT} \
  --region=${GCP_REGION} \
  --platform=managed \
  --format="value(status.address.url)" \
  --filter="metadata.name=grpc-calculator") 
ENDPOINT=${ENDPOINT#https://} && echo ${ENDPOINT}
```

Notice that this endpoint is secured with TLS even though the server we wrote 
uses a plaintext connection. Cloud Run provides a proxy that provides TLS for us.

We'll account for that in our `grpcurl` invocation by omitting the `-plaintext` flag:

```bash
grpcurl \
    -proto protos/calculator.proto \
    -d '{"first_operand": 2.0, "second_operand": 3.0, "operation": "ADD"}' \
    ${ENDPOINT}:443 \
    Calculator.Calculate
```

You have an auto-scaling gRPC-based calculator service!
