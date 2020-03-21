package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"os"

	pb "github.com/grpc-ecosystem/grpc-cloud-run-example/golang/protos"

	"google.golang.org/grpc"
)

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	grpcEndpoint := fmt.Sprintf(":%s", port)
	log.Printf("gRPC endpoint [%s]", grpcEndpoint)

	grpcServer := grpc.NewServer()
	pb.RegisterCalculatorServer(grpcServer, NewServer())

	ctx := context.Background()
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	listen, err := net.Listen("tcp", grpcEndpoint)
	if err != nil {
		log.Fatal(err)
	}
	log.Printf("Starting: gRPC Listener [%s]\n", grpcEndpoint)
	log.Fatal(grpcServer.Serve(listen))
}
