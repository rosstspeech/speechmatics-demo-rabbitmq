"""A rabbitmq producer which sends s3 URLs to a queue."""
import json
import logging
import os
import signal
import sys
import time
from typing import NoReturn, Union

import pika
from retry import retry

import aws

logging.basicConfig(level=logging.INFO)


def get_env(env_var: str, default_val: str = None, required: bool = False) -> Union[str, None]:
    """Handles when environment variables are set to an empty string.
    There's no way to not export unset env vars via docker/docker-compose.

    :param env_var: Environment variable name
    :type env_var: string

    :param default_val: value to use if not set, defaults to None
    :type default_val: string, optional

    :param required: Return KeyError if variable is not set, defaults to False
    :type required: bool, optional

    :return: environment variable value
    :rtype: string or None
    """

    if (value := os.environ.get(env_var, default_val)) not in ["", None]:
        return value
    else:
        if required:
            # Required but not set+no default behaves like os.environ[]
            raise KeyError
        else:
            # Otherwise behave like os.environ.get() but return our default.
            return default_val


@retry(pika.exceptions.AMQPConnectionError, delay=10)
def make_connection(rabbit_uri: str) -> pika.BlockingConnection:
    """Creates a rabbitmq connection.
    Exists to allow usage of @retry decorator.

    :param rabbit_uri: rabbitmq URI
    :type rabbit_uri: str

    :return: pika rabbitmq connection
    :rtype: pika.BlockingConnection
    """
    logging.info("Attempting to connect to rabbitmq")
    connection = pika.BlockingConnection(pika.URLParameters(rabbit_uri))
    logging.info("Connected to rabbitmq")
    return connection


def _shutdown(connection: pika.BlockingConnection = None) -> NoReturn:
    """Gracefully shutdown pika connection and app.
    This needs to exist because Docker sends SIGTERM, which Python doesn't handle for us.

    :param connection: pika connection to close
    :type connection: pika.BlockingConnection
    """
    if connection:
        try:
            connection.close()
        except pika.exceptions.ConnectionWrongStateError as exc:  # pylint: disable=unused-variable
            pass

    try:
        sys.exit(0)
    except SystemExit:
        os._exit(0)  # pylint: disable=protected-access


def main(rabbit_uri: str, rabbit_queue_name: str, s3_bucket_name: str, s3_file_prefix: str) -> None:
    """Creates signed urls for objects in an s3 bucket and adds them to a work queue.

    :param rabbit_uri: rabbitmq AMQP URI.
    :type rabbit_uri: string

    :param rabbit_queue_name: Name of message queue to utilize
    :type rabbit_queue_name: string

    :param s3_bucket_name: An S3 bucket.
    :type s3_bucket_name: string

    :param s3_file_prefix: Prefix of files to return. This is S3 for "directory." Defaults to "/", which means all.
    :type s3_file_prefix: string, optional
    """
    connection = make_connection(rabbit_uri)

    channel = connection.channel()
    channel.queue_declare(queue=rabbit_queue_name)

    messageNumber = 1
    try:
        logging.info(aws.get_s3_object_urls(s3_bucket_name, s3_file_prefix))
        for url in aws.get_s3_object_urls(s3_bucket_name, s3_file_prefix):
            messageBody = {}
            messageBody["jobId"] = str(messageNumber)
            messageBody["url"] = url

            logging.info("Submitting jobId: %s to queue", messageNumber)

            channel.basic_publish(exchange="", routing_key=rabbit_queue_name, body=json.dumps(messageBody))
            messageNumber += 1
            # time.sleep(2) #  Uncomment for demo
    except KeyboardInterrupt:
        pass
    finally:
        _shutdown(connection)


if __name__ == "__main__":
    env_rabbit_uri = get_env("RABBIT_URI", default_val="amqp://my-rabbit/%2F")
    env_rabbit_queue_name = get_env("RABBIT_QUEUE_NAME", default_val="speechmatics")
    env_s3_bucket_name = get_env("S3_BUCKET_NAME", required=True)  # This will intentionally error if not set.
    env_s3_file_prefix = get_env("S3_FILE_PREFIX", default_val="/")

    # Shutdown gracefully if SIGTERM is received (because Docker).
    signal.signal(signal.SIGTERM, _shutdown)  # type: ignore

    # Give rabbitmq server a moment to start.
    logging.info("Client started. Waiting 15 sec for rabbitmq to finish starting.")
    time.sleep(15)

    main(env_rabbit_uri, env_rabbit_queue_name, env_s3_bucket_name, env_s3_file_prefix)  # type: ignore
