import json
import socket
import time
import dsmq


def run(host="127.0.0.1", port=30008, n_iter=1000):
    mq = dsmq.connect_to_server(host=host, port=port)

    for i in range(n_iter):
        time.sleep(1)
        msg = f"{i}. Hello, world"
        topic = "greetings"
        mq.put(topic, msg)
        print(f"client sent {msg}")


if __name__ == "__main__":
    run()
