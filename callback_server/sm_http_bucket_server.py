"""
This module deals with running an HTTP server which captures arbitrary requests
so that they can be retrieved and inspected later.
"""
import argparse
import functools
import http
import time
import threading
import logging

import requests
import flask

APP = flask.Flask("http_bucket")
REQUESTS = []

ACTION_URL = "X-Action-Url"
ACTION_AUTH = "X-Action-Authorization"


def do_post_action(headers, job_id):
    if ACTION_URL not in headers:
        return {"error": f"{ACTION_URL} is required for a post action"}

    request_headers = {}
    if ACTION_AUTH in headers:
        request_headers["Authorization"] = headers[ACTION_AUTH]

    action_url = headers[ACTION_URL].replace("$jobid", job_id)

    res = requests.get(action_url, headers=request_headers)

    return {"status_code": res.status_code, "content": res.text}


def auth_middleware(f):
    """
    This middleware enforces that requests include an Authorization header in the format
    'Authorization: Bearer $auth_token' where auth_token is the token defined in the app config.
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if APP.config["auth"]:
            auth_token = APP.config["auth"]
            try:
                assert flask.request.headers["Authorization"] == f"Bearer {auth_token}"
            except:
                return ("Not authorized", http.HTTPStatus.FORBIDDEN)
        return f(*args, **kwargs)

    return wrapper


@APP.route("/", methods=["GET"])
@auth_middleware
def list_requests():
    """Lists all the requests that have been stored"""
    return flask.jsonify(REQUESTS)


@APP.route("/", methods=["POST", "PUT"])
@auth_middleware
def post_request():
    """Adds a new request to the store"""
    req = flask.request

    # Request data is passed as file attachments
    file_data = {}
    for (file_name, file_storage) in req.files.items():
        # Assume for convenience that the file is a text file.
        # However if utf-8 decoding fails treat it as binary.
        data = file_storage.stream.read()

        try:
            human_readable_data = data.decode("utf-8")
        except UnicodeDecodeError:
            human_readable_data = f"<binary data:{len(data)} bytes>"

        file_data[file_name] = human_readable_data
        file_storage.close()

    text_data = ""
    try:
        text_data = req.data.decode("utf-8")
    except UnicodeDecodeError:
        text_data = "decode error"

    # This fixes an occasional bug wherein the values of args in the request
    # are interpreted as lists rather than strings.
    #   e.g. {'args': {'id': ['7h6sxp6tbv'], 'status': ['success']}
    #   vs.  {'args': {'id': '7h6sxp6tbv',   'status': 'success'}
    args_dict = dict(req.args)
    for name, value in args_dict.items():
        if isinstance(value, list) and len(value) == 1:
            args_dict[name] = value[0]

    post_notify_action_response = None
    if "postnotifyaction" in args_dict:
        post_notify_action_response = do_post_action(req.headers, args_dict["id"])

    request = {
        "files": file_data,
        "text": text_data,
        "headers": dict(req.headers),
        "method": req.method,
        "time": int(time.time()),
        "remote_addr": req.remote_addr,
    }

    REQUESTS.insert(0, request)

    # Store a limited number of requests
    if len(REQUESTS) > 100:
        REQUESTS.pop()

    return ("ok", http.HTTPStatus.OK)


def run_server(host="0.0.0.0", port=8080, debug=False, run_async=False, auth=None, silent=False):
    """Runs the http bucket
    Args:
        host (str): Which host to run on
        port (int): Which port to run on
        debug (bool): Whether to run the server in debug mode
        run_async (bool): Whether to run the server in a new thread. This function will block
            indefinitely if run_async=False
        silent (bool): Whether to suppress logging output from the server
    """
    if run_async:
        thread = threading.Thread(
            name="http_bucket_thread",
            target=run_server,
            kwargs={"host": host, "port": port, "run_async": False, "silent": silent},
        )
        thread.daemon = True
        thread.start()
    else:
        if silent:
            APP.logger.disabled = True
            logging.getLogger("werkzeug").disabled = True

        # This causes 'jsonify' to pretty-print the json response. Useful for browsers.
        APP.config["JSONIFY_PRETTYPRINT_REGULAR"] = True
        APP.config["auth"] = auth
        APP.run(host=host, port=port, debug=debug, threaded=False)


def main():
    """Main function which parses arguments and runs the http bucket"""
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0", help="Which host to run the server on.")
    parser.add_argument("--port", default=8080, type=int, help="Which port to run the server on.")
    parser.add_argument("--debug", default=False, type=bool, help="Whether to run the server in debug mode.")
    parser.add_argument(
        "--auth", default=None, type=str, help="An auth token to require for requests: Authorization: Bearer $token"
    )
    args = parser.parse_args()

    run_server(host=args.host, port=args.port, debug=args.debug, auth=args.auth, silent=False)


if __name__ == "__main__":
    main()
