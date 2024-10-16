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
            msg = json.dumps({"action": "get", "topic": "greetings"})
            s.sendall(bytes(msg, "utf-8"))
            data = s.recv(1024)
            if not data:
                raise RuntimeError("Connection terminated by server")
            msg_str = data.decode("utf-8")
            print(f"received {json.loads(msg_str)}")


if __name__ == "__main__":
    main()
