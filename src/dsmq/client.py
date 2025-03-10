import json
import time
from websockets.sync.client import connect as ws_connect
from websockets.exceptions import ConnectionClosedError

_default_host = "127.0.0.1"
_default_port = 30008

_n_retries = 10
_initial_retry = 0.01  # seconds
_shutdown_delay = 0.1  # seconds


def connect(host=_default_host, port=_default_port, verbose=False):
    return DSMQClientSideConnection(host, port, verbose=verbose)


class DSMQClientSideConnection:
    def __init__(self, host, port, verbose=False):
        self.uri = f"ws://{host}:{port}"
        self.verbose = verbose
        if self.verbose:
            print(f"Connecting to dsmq server at {self.uri}")
        for i_retry in range(_n_retries):
            try:
                self.websocket = ws_connect(self.uri)
                break
            except ConnectionRefusedError:
                self.websocket = None
                # Exponential backoff
                # Wait twice as long each time before trying again.
                time.sleep(_initial_retry * 2**i_retry)
                if self.verbose:
                    print("    ...trying again")

        if self.websocket is None:
            raise ConnectionRefusedError("Could not connect to dsmq server.")

        self.time_of_last_request = time.time()

    def get(self, topic):
        msg = {"action": "get", "topic": topic}
        self.websocket.send(json.dumps(msg))
        try:
            msg_text = self.websocket.recv()
        except ConnectionClosedError:
            self.close()
            return ""

        msg = json.loads(msg_text)
        return msg["message"]

    def get_wait(self, topic):
        """
        A variant of `get()` that retries a few times until it gets
        a non-empty message. Adjust `_n_tries` and `_initial_retry`
        to change how persistent it will be.
        """
        for i_retry in range(_n_retries):
            message = self.get(topic)
            if message != "":
                return message
            time.sleep(_initial_retry * 2**i_retry)
        return message

    def put(self, topic, msg_body):
        msg_dict = {"action": "put", "topic": topic, "message": msg_body}
        self.websocket.send(json.dumps(msg_dict))

    def shutdown_server(self):
        msg_dict = {"action": "shutdown", "topic": ""}
        self.websocket.send(json.dumps(msg_dict))
        # Give the server time to wind down
        time.sleep(_shutdown_delay)

    def close(self):
        self.websocket.close()
        # Give the websocket time to wind down
        time.sleep(_shutdown_delay)
