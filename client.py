import argparse
import functools

from typing import Text

import grpc

import calculator_pb2
import calculator_pb2_grpc


_OPERATIONS = {
    "add": calculator_pb2.ADD,
    "subtract": calculator_pb2.SUBTRACT,
}


def _calculate(server_address: Text,
               operation: calculator_pb2.Operation,
               a: float,
               b: float,
               plaintext: bool) -> float:
    if plaintext:
        channel = grpc.insecure_channel(server_address)
    else:
        channel = grpc.secure_channel(server_address, grpc.ssl_channel_credentials())
    try:
        stub = calculator_pb2_grpc.CalculatorStub(channel)
        request = calculator_pb2.BinaryOperation(first_operand=a,
                                                 second_operand=b,
                                                 operation=operation)
        return stub.Calculate(request).result
    finally:
        channel.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("server",
                        help="The address of the calculator server.")
    parser.add_argument("operation",
                        choices=_OPERATIONS.keys(),
                        help="The operation to perform")
    parser.add_argument("a", type=float, help="The first operand.")
    parser.add_argument("b", type=float, help="The second operand.")
    parser.add_argument("-k", "--plaintext",
                        action="store_true",
                        help="When set, establishes a plaintext connection. " +
                             "Useful for debugging locally.")
    args = parser.parse_args()
    print(_calculate(args.server,
                     _OPERATIONS[args.operation],
                     args.a, args.b, args.plaintext))
