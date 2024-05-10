FROM python:3.10-alpine

COPY sm_http_bucket_server.py /app/

COPY requirements.txt /tmp
RUN python3 -m pip install -r /tmp/requirements.txt

ENTRYPOINT [ "python3" ]
CMD ["-u", "/app/sm_http_bucket_server.py"]
