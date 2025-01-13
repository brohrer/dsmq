import json
from websockets.sync.client import connect as ws_connect

_default_host = "127.0.0.1"
_default_port = 30008


def connect(host=_default_host, port=_default_port):
    return DSMQClientSideConnection(host, port)


class DSMQClientSideConnection:
    def __init__(self, host, port):
        self.uri = f"ws://{host}:{port}"
        self.websocket = ws_connect(self.uri)

    def get(self, topic):
        msg = {"action": "get", "topic": topic}
        self.websocket.send(json.dumps(msg))

        msg_text = self.websocket.recv()
        msg = json.loads(msg_text)
        return msg["message"]

    def put(self, topic, msg_body):
        msg_dict = {"action": "put", "topic": topic, "message": msg_body}
        self.websocket.send(json.dumps(msg_dict))
