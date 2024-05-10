"""A rabbitmq consumer which transcribes audio files from a URL."""
import asyncio
import json
import logging
import os
import signal
import sys
import time
from asyncio import AbstractEventLoop
from typing import NoReturn, Union

import aio_pika
import aiofiles
from aioretry import RetryInfo, RetryPolicyStrategy, retry

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


def retry_policy(info: RetryInfo) -> RetryPolicyStrategy:  # pylint: disable=unused-argument
    """Creates policy for aioretry decorator.
    This policy:
    - will always retry until success
    - retries after 10 seconds
    """
    return False, 10


@retry(retry_policy)
async def make_connection(rabbit_uri: str) -> aio_pika.abc.AbstractRobustConnection:
    """Creates a rabbitmq connection.
    Exists to allow usage of @retry decorator.

    :param rabbit_uri: rabbitmq URI
    :type rabbit_uri: str

    :return: aio_pika rabbitmq connection
    :rtype: aio_pika.Connection
    """
    logging.info("Attempting to connect to rabbitmq")
    connection = await aio_pika.connect_robust(rabbit_uri)
    logging.info("Connected to rabbitmq")
    return connection


async def start_transcription(message: str, callback_server: str) -> None:
    """Transcribes file from message queue and posts the result to a callback server.

    :param message: JSON string containing URL of audio to be fetched.
        Format:
            {
              "jobId" =  // ID: string
              "url" =  // Audio fetch URL
            }
    :type message: string

    :param callback_server: URL to post completed transcript
    :type callback_server: string
    """
    logging.info("rabbitmq message %s", message)
    message_content = json.loads(message)
    job_id = message_content["jobId"]

    job_config = {
        "type": "transcription",
        "transcription_config": {"language": "en"},
        "fetch_data": {"url": message_content["url"]},
        "notification_config": [{"url": callback_server, "contents": ["transcript.txt","transcript.json-v2"]}],
    }

    logging.info("Received Job ID: %s", job_id)

    config_file = "/opt/orchestrator/config.json"

    async with aiofiles.open(config_file, mode="wt", encoding="utf-8") as f:
        await f.write(json.dumps(job_config))

    logging.info("Starting Transcription Process for Job ID %s", job_id)

    pipeline = await asyncio.create_subprocess_exec(
        "pipeline", "--job-config", config_file, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await pipeline.communicate()

    if stdout:
        logging.info("stdout: %s", stdout.decode())
    if stderr:
        logging.info("stderr: %s", stderr.decode())

    logging.info("Completed Transcription Process for Job ID %s, exit code %s", job_id, pipeline.returncode)


def _shutdown(loop: AbstractEventLoop = None) -> NoReturn:
    logging.critical("Receiver shutting down")
    if loop and loop.is_running():
        loop.stop()

    try:
        sys.exit(0)
    except SystemExit:
        os._exit(0)  # pylint: disable=protected-access


async def main(rabbit_uri: str, rabbit_queue_name: str, callback_server: str) -> None:
    """Waits for/processes rabbitmq messages.

    :param rabbit_uri: AMQP URI
    :type rabbit_uri: string

    :param rabbit_queue_name: AMQP queue
    :type rabbit_queue_name: string

    :param callback_server: URL to post completed transcript
    :type callback_server: string
    """

    logging.info("Receiver started")
    connection = await make_connection(rabbit_uri)

    async def callback(message: aio_pika.IncomingMessage) -> None:
        """Callback executed for each job taken from queue."""
        message_body = message.body
        logging.info("Transcribing: %s", message_body)
        await start_transcription(message_body, callback_server)
        await message.ack()

    async with await connection.channel() as channel:
        await channel.set_qos(prefetch_count=1)
        queue = await channel.declare_queue(rabbit_queue_name)
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                await callback(message)


if __name__ == "__main__":
    env_rabbit_uri = get_env("RABBIT_URI", default_val="amqp://my-rabbit/%2F")
    env_rabbit_queue_name = get_env("RABBIT_QUEUE_NAME", default_val="speechmatics")
    env_callback_server = get_env("CALLBACK_SERVER", default_val="http://callback-server:8080")

    # rabbitmq server takes a while to start.
    logging.info("Receiver starting - waiting 15 sec for rabbitmq startup.")
    time.sleep(15)

    event_loop = asyncio.get_event_loop()

    for signal in [signal.SIGINT, signal.SIGTERM]:  # type: ignore
        event_loop.add_signal_handler(signal, _shutdown)  # type: ignore

    event_loop.run_until_complete(main(env_rabbit_uri, env_rabbit_queue_name, env_callback_server))  # type: ignore
