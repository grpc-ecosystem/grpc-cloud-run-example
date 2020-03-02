# gRPC in Google Cloud Run

*Estimated Reading Time: 20 minutes*

Google Cloud Run makes it easy to deploy and run REST servers, but it also
supports gRPC servers out of the box. This article will show you how to
deploy a gRPC service written in Python to Cloud Run. For the full code, [check
out the Github repo.](https://github.com/grpc-ecosystem/grpc-cloud-run-example)

We'll be writing a simple remote calculator service. For the moment, it will
just support adding and subtracting floating point numbers, but once this is up
and running, you could easily extend it to add other features.

To get started, choose the language you'll be building your server in.

 - [Node](node/README.md)
 - [Python](python/README.md)
