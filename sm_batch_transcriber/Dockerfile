ARG TRANSCRIBER_VERSION
FROM speechmatics-docker-public.jfrog.io/batch-asr-transcriber-en:${TRANSCRIBER_VERSION}

# Expects the parent directory as build context
# BUILD_DIR specifies the location of the app files.
ARG BUILD_DIR

WORKDIR /opt/orchestrator

RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get install -y python3-pip \
    && apt-get autoremove -y && apt-get clean -y && rm -rf /var/lib/apt/lists/*

COPY ./${BUILD_DIR}/*.py /app/
COPY ./${BUILD_DIR}/requirements.txt /tmp/requirements.txt
RUN python3 -m pip install -r /tmp/requirements.txt

ENTRYPOINT [ "python3", "-u", "/app/rabbitmq_receiver_with_pipeline.py"]