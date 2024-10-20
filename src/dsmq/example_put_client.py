import json
import socket
import time


def run(host="127.0.0.1", port=30008, n_iter=1000):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))

        for i in range(n_iter):
            time.sleep(1)
            note = f"{i}. Hello, world"
            msg = json.dumps({"action": "put", "topic": "greetings", "message": note})
            s.sendall(bytes(msg, "utf-8"))
            print(f"client sent {msg}")


if __name__ == "__main__":
    run()
