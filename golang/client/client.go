package main

import (
	"context"

	pb "github.com/grpc-ecosystem/grpc-cloud-run-example/golang/protos"

	"google.golang.org/grpc"
)

// Client is a struct that implements the pb.CalculatorClient
type Client struct {
	client pb.CalculatorClient
}

// NewClient returns a new Client
func NewClient(conn *grpc.ClientConn) *Client {
	return &Client{
		client: pb.NewCalculatorClient(conn),
	}
}

// Calculate performs an operation on operands defined by pb.BinaryOperation returning pb.CalculationResult
func (c *Client) Calculate(ctx context.Context, r *pb.BinaryOperation) (*pb.CalculationResult, error) {
	return c.client.Calculate(ctx, r)
}
