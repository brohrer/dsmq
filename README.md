# Dead Simple Message Queue

### Install

```bash
pip install dsmq
```

### Create a dsmq server

As in `example_server.py`

```python
from dsmq import dsmq

dsmq.serve(host="127.0.0.1", port=12345)
```

### Add a message to a queue

As in `example_put_client.py`

```python
import json
import socket

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect(("127.0.0.1", 12345))
    message_content = {"action": "put", "topic": "greetings", "message": "Hello!"}
    msg = json.dumps(message_content)
    s.sendall(bytes(msg, "utf-8"))
```

### Read a message from a queue


```python
import json
import socket

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect(("127.0.0.1", 12345))

    for i in range(n_iter):
        request_message_content = {"action": "get", "topic": "greetings"}
        request_msg = json.dumps(request_message_content)
        s.sendall(bytes(reequest_msg, "utf-8"))

        reply_msg = s.recv(1024)
        if not reply_msg:
            raise RuntimeError("Connection terminated by server")
        reply_msg_content = reply_msg.decode("utf-8")
```

### Demo

1. Open 3 separate terminal windows.
1. In the first, run `example_server.py`.
1. In the second, run `example_put_client.py`.
1. In the third, run `example_get_client.py`.
