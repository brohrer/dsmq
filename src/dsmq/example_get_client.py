import json
import time
import dsmq


def run(host="127.0.0.1", port=30008, n_iter=1000):
    mq = dsmq.connect_to_server(host=host, port=port)

    for i in range(n_iter):
        time.sleep(1)
        msg = mq.get("greetings")
        print(f"client received {msg}")


if __name__ == "__main__":
    run()
