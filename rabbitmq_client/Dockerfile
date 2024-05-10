FROM python:3.10-alpine

# Expects the parent directory as build context
# BUILD_DIR specifies the location of the app files.
ARG BUILD_DIR

WORKDIR /app

COPY ./${BUILD_DIR}/*.py /app/

COPY ./${BUILD_DIR}/requirements.txt /tmp/requirements.txt
RUN python3 -m pip install -r /tmp/requirements.txt

ENTRYPOINT [ "python3", "-u", "/app/rabbitmq_client.py"]