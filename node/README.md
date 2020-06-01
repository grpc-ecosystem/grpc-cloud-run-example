# gRPC in Google Cloud Run

*Estimated Reading Time: 20 minutes*

Google Cloud Run makes it easy to deploy and run REST servers, but it also
supports gRPC servers out of the box. This article will show you how to
deploy a gRPC service written in Node.js to Cloud Run. For the full code, [check
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

Let's start with the server. Take a look at [`server.js`](server.js) for the full code.
Google Cloud Run will set up an environment variable called `PORT` on which your
server should listen. The first thing we do is pull that from the environment:

```node
const PORT = process.env.PORT;
```

Next, we set up a server bound to that port, listening on all interfaces.

```node
function main() {
  const server = new grpc.Server();
  server.addService(calculatorProto.Calculator.service, {calculate});
  server.bindAsync(`0.0.0.0:${PORT}`, grpc.ServerCredentials.createInsecure(), (error, port) => {
    if (error) {
      throw error;
    }
    server.start();
  });
}
```

Notice that we use the `createInsecure` method here. Google Cloud Run's proxy
provides us with a TLS-encrypted proxy that handles the messy business of
setting up certs for us. The traffic from the proxy to the container with our
gRPC server in it goes through an encrypted tunnel, so we don't need to worry
about handling it ourselves. Cloud Run natively handles HTTP/2, so gRPC's
transport is well-supported.

## Connecting

Now let's test the server out locally. First, we install dependencies.

```bash
npm install
```

And then we start the server:

```bash
export PORT=50051
node server.js
```

Now the server should be listening on port `50051`. We'll use the tool
[`grpcurl`](https://github.com/fullstorydev/grpcurl) to manually interact with it.
On Linux and Mac you can install it with `curl -s https://grpc.io/get_grpcurl | bash`.

```bash
grpcurl \
    -d '{"first_operand": 2.0, "second_operand": 3.0, "operation": "ADD"}' \
    --plaintext \
    -proto calculator.proto \
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

We're going to use the official Dockerhub Node 12.14 image as our base image.

```Dockerfile
FROM node:12.14
```

We'll put all of our code in `/srv/grpc/`.

```Dockerfile
WORKDIR /srv/grpc

COPY server.js *.proto package.json .
```

We install our Node dependencies into the container.

```Dockerfile
RUN npm install
```

Finally, we set our container up to run the server by default.

```Dockerfile
CMD ["node", "server.js"]
```

Now we can build our image. In order to deploy to Cloud Run, we'll be pushing to
the `gcr.io` container registry, so we'll tag it accordingly.

```bash
export GCP_PROJECT=<Your GCP Project Name>
docker build -t gcr.io/$GCP_PROJECT/grpc-calculator:latest
```

The tag above will change based on your GCP project name. We're calling the
service `grpc-calculator` and using the `latest` tag.

Now, before we deploy to Cloud Run, let's make sure that we've containerized our
application properly. We'll test it by spinning up a local container.

```bash
docker run -d -p 50051:50051 -e PORT=50051 gcr.io/$GCP_PROJECT/grpc-calculator:latest
```

If all goes well, `grpcurl` will give us the same result as before:

```bash
grpcurl \
    -d '{"first_operand": 2.0, "second_operand": 3.0, "operation": "ADD"}' \
    --plaintext \
    -proto calculator.proto \
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
gcloud run deploy --image gcr.io/$GCP_PROJECT/grpc-calculator:latest --platform managed
```

You may be prompted for auth. If so, choose the unauthenticated option.

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

Notice that this endpoint is secured with TLS even though the server we wrote uses a plaintext connection. Cloud Run provides a proxy that provides TLS for us.

We'll account for this in our `grpcurl` invocation by omitting the `-plaintext` flag:

```bash
grpcurl \
    -proto calculator.proto \
    -d '{"first_operand": 2.0, "second_operand": 3.0, "operation": "ADD"}' \
    ${ENDPOINT}:443 \
    Calculator.Calculate
```

Ensure that you run the above command in a directory relative to the file specified under the `-proto` flag.

And now you've got an auto-scaling calculator gRPC service!
