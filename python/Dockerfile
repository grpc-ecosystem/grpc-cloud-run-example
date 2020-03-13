FROM python:3.8

WORKDIR /srv/grpc

COPY server.py *.proto requirements.txt ./

RUN pip install -r requirements.txt && \
    python -m grpc_tools.protoc \
        -I. \
        --python_out=. \
        --grpc_python_out=. \
        calculator.proto

CMD ["python", "server.py"]
