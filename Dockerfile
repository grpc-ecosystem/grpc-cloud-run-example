FROM python:3.8

ENV SRV_DIR "/srv/grpc"

RUN mkdir -p "${SRV_DIR}"

WORKDIR "${SRV_DIR}"

COPY serverpy *.proto requirements.txt "${SRV_DIR}/"

RUN pip install -r requirements.txt && \
    python -m grpc_tools.protoc \
        -I. \
        --python_out=. \
        --grpc_python_out=. \
        calculator.proto

CMD ["python", "server.py"]
