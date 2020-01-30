import logging
import os
from concurrent import futures

from typing import Text

import calculator_pb2
import calculator_pb2_grpc

import grpc

_PORT = os.environ.get("PORT", "50051")

class Calculator(calculator_pb2_grpc.CalculatorServicer):

    @staticmethod
    def _add(a: float, b: float) -> float:
        return a + b

    @staticmethod
    def _subtract(a: float, b: float) -> float:
        return a - b

    def Calculate(self,
                  request: calculator_pb2.BinaryOperation,
                  context: grpc.ServicerContext) -> None:
        logging.info("Received request: %s", request)
        if request.operation == calculator_pb2.ADD:
            result = Calculator._add(request.first_operand, request.second_operand)
        else:
            result = Calculator._subtract(request.first_operand, request.second_operand)
        return calculator_pb2.CalculationResult(result=result)


def _serve(port: Text):
    bind_address = f"[::]:{port}"
    server = grpc.server(futures.ThreadPoolExecutor())
    calculator_pb2_grpc.add_CalculatorServicer_to_server(Calculator(), server)
    server.add_insecure_port(bind_address)
    server.start()
    logging.info("Listening on %s.", bind_address)
    server.wait_for_termination()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _serve(_PORT)
