# gRPC in Google Cloud Run

*Estimated Reading Time: 20 minutes*

Google Cloud Run makes it easy to deploy and run REST servers, but it also
supports gRPC servers out of the box. This article will show you how to
deploy a gRPC service written in Golang to Cloud Run. For the full code, [check
out the Github repo.](https://github.com/grpc-ecosystem/grpc-cloud-run-example)

We'll be writing a simple remote calculator service. For the moment, it will
just support adding and subtracting floating point numbers, but once this is up
and running, you could easily extend it to add other features.

## The Protocol Buffer Definition

Take a look in [`calculator.proto`](https://github.com/grpc-ecosystem/grpc-cloud-run-example/blob/master/golang/protos/calculator.proto) to see the full protocol buffer definition. If
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

Let's start with the server. Take a look at [`main.go`](https://github.com/grpc-ecosystem/grpc-cloud-run-example/blob/master/golang/server/main.go) and [`server.go`](https://github.com/grpc-ecosystem/grpc-cloud-run-example/blob/master/golang/server/server.go).
Google Cloud Run will set up an environment variable called `PORT` on which your
server should listen. The first thing we do is pull that from the environment:

```golang
port := os.Getenv("PORT")
```

Next, we set up a server bound to that port, listening on all interfaces.

```golang
grpcServer := grpc.NewServer()
pb.RegisterCalculatorServer(grpcServer, NewServer())

...

listen, err := net.Listen("tcp", grpcEndpoint)
if err != nil {
	log.Fatal(err)
}
log.Printf("Starting: gRPC Listener [%s]\n", grpcEndpoint)
log.Fatal(grpcServer.Serve(listen))
```

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

# This compiles the Golang plugin to ${GOPATH}/bin
go get -u github.com/golang/protobuf/protoc-gen-go
```

Now we generate Golang code from the `calculator.proto` file. This is how
we get the definitions for our `calculator.pb.go`.

```bash
protoc \
--proto_path=. \
--go_out=plugins=grpc:. \
./protos/calculator.proto
```

Finally, we start the server:

```bash
export PORT=50051
go run github.com/grpc-ecosystem/grpc-cloud-run-example/golang/server
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

We're going to use the official Dockerhub Golang [1.13.9-buster](https://hub.docker.com/layers/golang/library/golang/1.13.9-buster/images/sha256-205d5cf61216a16da4431dd5796793c650236159fa04e055459940ddc4c6389c?context=explore) image as our base image.

```Dockerfile
FROM golang@sha256:205d5cf61216a16da4431dd5796793c650236159fa04e055459940ddc4c6389c
```

We'll put all of our code in `/srv/grpc/`.

```Dockerfile
WORKDIR /srv/grpc

COPY go.mod .
COPY protos/calculator.proto ./protos/
COPY server/*.go ./server/
```

We install protoc and protoc-gen-go and generate the Golang sources.


```Dockerfile
ARG VERS="3.11.4"
ARG ARCH="linux-x86_64"
RUN wget https://github.com/protocolbuffers/protobuf/releases/download/v${VERS}/protoc-${VERS}-${ARCH}.zip \
      --output-document=./protoc-${VERS}-${ARCH}.zip && \
    apt update && apt install -y unzip && \
    unzip -o protoc-${VERS}-${ARCH}.zip -d protoc-${VERS}-${ARCH} && \
    mv protoc-${VERS}-${ARCH}/bin/* /usr/local/bin && \
    mv protoc-${VERS}-${ARCH}/include/* /usr/local/include && \
    go get -u github.com/golang/protobuf/protoc-gen-go

# Generates the Golang protobuf files
RUN protoc \
    --proto_path=. \
    --go_out=plugins=grpc:. \
    ./protos/*.proto
```

We compile to a static binary:

```Dockerfile
RUN CGO_ENABLED=0 GOOS=linux \
    go build -a -installsuffix cgo \
    -o /go/bin/server \
    github.com/grpc-ecosystem/grpc-cloud-run-example/golang/server
```

Then we move the binary into a runtime container:

```Dockerfile
FROM scratch

COPY --from=build /go/bin/server /server
```

And set the container to run the server by default.

```Dockerfile
ENTRYPOINT ["/server"]
```

Now we can build our image. In order to deploy to Cloud Run, we'll be pushing to
the `gcr.io` container registry, so we'll tag it accordingly.

```bash
GCP_PROJECT=<Your GCP Project Name>
docker build \
  --tag=gcr.io/${GCP_PROJECT}/grpc-calculator:latest \
  --file=./Dockerfile \
  .
```

> **NB** Don't forget that final `.`, it's critical

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

There's a simple Golang client too:

```bash
go run github.com/grpc-ecosystem/grpc-cloud-run-example/golang/client \
--gprc_endpoint=${ENDPOINT}:443
```

You have an auto-scaling gRPC-based calculator service!
