import json
import socket
import sqlite3
import sys
from threading import Thread
import time

N_RETRIES = 5
FIRST_RETRY = 0.01  # seconds


def run(host="127.0.0.1", port=30008):
    sqlite_conn = sqlite3.connect("file:mem1?mode=memory&cache=shared")
    cursor = sqlite_conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (timestamp DOUBLE, topic TEXT, message TEXT)
    """)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Setting this socket option to re-use the address,
        # even if it's already in use.
        # This is helpful in recovering from crashes where things didn't
        # shut down properly.
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        s.bind((host, port))
        s.listen()

        print()
        print(f"Server started at {host} on port {port}.")
        print("Waiting for clients...")

        while True:
            socket_conn, addr = s.accept()
            print(f"Connected by {addr}")
            Thread(target=handle_socket, args=(socket_conn,)).start()

    sqlite_conn.close()


def handle_socket(socket_conn):
    sqlite_conn = sqlite3.connect("file:mem1?mode=memory&cache=shared")
    cursor = sqlite_conn.cursor()

    creation_time = time.time()
    last_read = {}

    while True:
        data = socket_conn.recv(1024)
        # Check whether the connection has been terminated
        if not data:
            break

        msg_str = data.decode("utf-8")
        try:
            # print("dsmq received ", msg_str)
            msg = json.loads(msg_str)
        except json.decoder.JSONDecodeError:
            print("Message must be json-friendly")
            print(f"    Received: {msg}")
            continue

        topic = msg["topic"]
        timestamp = time.time()

        if msg["action"] == "put":
            msg["timestamp"] = timestamp

            # This block allows for multiple retries if the database
            # is busy.
            for i_retry in range(N_RETRIES):
                try:
                    cursor.execute(
                        """
INSERT INTO messages (timestamp, topic, message)
VALUES (:timestamp, :topic, :message)
                        """,
                        (msg),
                    )
                    sqlite_conn.commit()
                except sqlite3.OperationalError:
                    wait_time = FIRST_RETRY * 2**i_retry
                    time.sleep(wait_time)
                    continue
                break

        elif msg["action"] == "get":
            try:
                last_read_time = last_read[topic]
            except KeyError:
                last_read[topic] = creation_time
                last_read_time = last_read[topic]
            msg["last_read_time"] = last_read_time

            # This block allows for multiple retries if the database
            # is busy.
            for i_retry in range(N_RETRIES):
                try:
                    cursor.execute(
                        """
SELECT message,
timestamp
FROM messages,
(
SELECT MIN(timestamp) AS min_time
FROM messages
WHERE topic = :topic
    AND timestamp > :last_read_time
) a
WHERE topic = :topic
AND timestamp = a.min_time
                        """,
                        msg,
                    )
                except sqlite3.OperationalError:
                    wait_time = FIRST_RETRY * 2**i_retry
                    time.sleep(wait_time)
                    continue
                break

            try:
                result = cursor.fetchall()[0]
                message = result[0]
                timestamp = result[1]
                last_read[topic] = timestamp
            except IndexError:
                # Handle the case where no results are returned
                message = ""

            msg = json.dumps({"message": message})
            socket_conn.sendall(bytes(msg, "utf-8"))
        else:
            print("Action must either be 'put' or 'get'")

    sqlite_conn.close()


if __name__ == "__main__":
    if len(sys.argv) == 3:
        host = sys.argv[1]
        port = int(sys.argv[2])
        run(host=host, port=port)
    elif len(sys.argv) == 2:
        host = sys.argv[1]
        run(host=host)
    elif len(sys.argv) == 1:
        run()
    else:
        print(
            """
Try one of these:
$ python3 dsmq.py

$ python3 dsmq.py 127.0.0.1

$ python3 dsmq.py 127.0.0.1 25853

            """
        )
