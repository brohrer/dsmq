# Dead Simple Message Queue

## What it does

Part mail room, part bulletin board, dsmq is a central location for sharing messages
between processes, even when they are running on computers scattered around the world.

Its defining characteristic is bare-bones simplicity.

## How to use it

### Install

```bash
pip install dsmq
```
### Create a dsmq server

As in `src/dsmq/example_server.py`

```python
from dsmq.server import serve

serve(host="127.0.0.1", port=30008)
```

### Connect a client to a dsmq server

As in `src/dsmq/example_put_client.py`

```python
from dsmq.client import connect

mq = connect(host="127.0.0.1", port=12345)
```
### Add a message to a queue

As in `src/dsmq/example_put_client.py`

```python
topic = "greetings"
msg = "hello world!"
mq.put(topic, msg)
```

### Read a message from a queue

As in `src/dsmq/example_get_client.py`

```python
topic = "greetings"
msg = mq.get(topic)
```

### Spin up and shut down a dsmq in its own process

A dsmq server doesn't come with a built-in way to shut itself down. 
It can be helpful to have it running in a separate process that can be
managed

```python
import multiprocessing as mp

p_mq = mp.Process(target=serve, args=(config.MQ_HOST, config.MQ_PORT))
p_mq.start()

p_mq.join()
# or 
p_mq.kill()
p_mq.close()
```

### Demo

1. Open 3 separate terminal windows.
1. In the first, run `src/dsmq/server.py` as a script.
1. In the second, run `src/dsmq/example_put_client.py`.
1. In the third, run `src/dsmq/example_get_client.py`.

Alternatively, you can run them all at once with `src/dsmq/demo.py`.

## How it works

### Expected behavior and limitations

- Many clients can read messages of the same topic. It is a one-to-many
publication model.

- A client will not be able to read any of the messages that were put into
a queue before it connected.

- A client will get the oldest message available on a requested topic.
Queues are first-in-first-out.

- Messages older than 600 seconds will be deleted from the queue.

- Put and get operations are fairly quick--less than 100 $`\mu`$s of processing
time plus any network latency--so it can comfortably handle requests at rates of
hundreds of times per second. But if you have several clients reading and writing
at 1 kHz or more, you may overload the queue.

- The queue is backed by an in-memory SQLite database. If your message volumes
get larger than your RAM, you will reach an out-of-memory condition.


# API Reference
[[source](https://github.com/brohrer/dsmq/blob/main/src/dsmq/serve.py)]

### `serve(host="127.0.0.1", port=30008)`

Kicks off the mesage queue server. This process will be the central exchange
for all incoming and outgoing messages.
- `host` (str), IP address on which the server will be visible and
- `port` (int), port. These will be used by all clients.
Non-privileged ports are numbered 1024 and higher.

### `connect(host="127.0.0.1", port=30008)`

Connects a client to an existing message queue server.
- `host` (str), IP address of the *server*.
- `port` (int), port on which the server is listening.
- returns a `DSMQClientSideConnection` object.

## `DSMQClientSideConnection` class

This is a convenience wrapper, to make the `get()` and `put()` functions
easy to write and remember. It's under the hood only, not meant to be called directly.

### `put(topic, msg)`

Puts `msg` into the queue named `topic`. If the queue doesn't exist yet, it is created.
- msg (str), the content of the message.
- topic (str), name of the message queue in which to put this message.

### `get(topic)`

Get the oldest eligible message from the queue named `topic`.
The client is only elgibile to receive messages that were added after it
connected to the server.
- `topic` (str)
- returns str, the content of the message. If there was no eligble message
in the topic, or the topic doesn't yet exist,
returns `""`.

### `get_wait(topic)`

A variant of `get()` that retries a few times until it gets
a non-empty message. Adjust internal values `_n_tries` and `_initial_retry`
to change how persistent it will be.

- `topic` (str)
- returns str, the content of the message. If there was no eligble message
in the topic after the allotted number of tries,
or the topic doesn't yet exist,
returns `""`.

### `shutdown_server()`

Gracefully shut down the server, through the client connection.

### `close()`

Gracefully shut down the client connection.

# Testing

Run all the tests in `src/dsmq/tests/` with pytest, for example
```
uv run pytest
```

# Performance characterization

Time typical operations on your system with the script at
`src/dsmq/tests/performance_suite.py`
