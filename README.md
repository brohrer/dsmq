# Dead Simple Message Queue

## What it does

TODO:
dsmq is a central location

## How to use it

### Install

```bash
pip install dsmq
```
### Create a dsmq server

As in `src/dsmq/example_server.py`

```python
from dsmq import dsmq

dsmq.serve(host="127.0.0.1", port=12345)
```

### Add a message to a queue

As in `src/dsmq/example_put_client.py`

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

As in `src/dsmq/example_get_client.py`

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
1. In the first, run `src/dsmq/example_server.py`.
1. In the second, run `src/dsmq/example_put_client.py`.
1. In the third, run `src/dsmq/example_get_client.py`.


## How it works

### Expected behavior and limitations

- Many clients can read messages of the same topic. It is a one-to-many
pulication model.

- A get client will not be able to read any of the messages that were put into
the queue before it started.

- A client will get the oldest message available on a requested topic.
Queues are first-in-first-out.

- Put and get operations are fairly quick--less than 100 `$\mu$`s of processing
time plus any network latency-so it can comfortably handle operations at
hundreds of Hz. But if you try to have several read and write clients running
at 1 kHz or more, you may overload the queue.

- The queue is backed by an in-memory SQLite database. If your message volumes
get larger than your RAM, you may reach an out-of-memory condition.


# API Reference


TODO:
