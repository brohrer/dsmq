import json
import socket
import time

HOST = "127.0.0.1"
PORT = 12345


def main():
    n_iter = 1000

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))

        for i in range(n_iter):
            time.sleep(1)
            note = f"{i}. Hello, world"
            msg = json.dumps({"action": "put", "topic": "greetings", "message": note})
            s.sendall(bytes(msg, "utf-8"))
            print(f"sent {msg}")


if __name__ == "__main__":
    main()
