import json
import socket
import sqlite3
import sys
from threading import Thread
import time

_default_host = "127.0.0.1"
_default_port = 30008

_message_length_offset = 1_000_000
_header_length = 23
_n_retries = 5
_first_retry = 0.01  # seconds
_time_to_live = 600.0  # seconds


def start_server(host=_default_host, port=_default_port):
    """
    For best results, start this running in its own process and walk away.
    """
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
            Thread(target=_handle_client_connection, args=(socket_conn,)).start()

    sqlite_conn.close()


def connect_to_server(host=_default_host, port=_default_port):
    return DSMQClientSideConnection(host, port)


class DSMQClientSideConnection:
    def __init__(self, host, port):
        self.dsmq_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.dsmq_conn.connect((host, port))

    def get(self, topic):
        msg_dict = {"action": "get", "topic": topic}
        _send_message(self.dsmq_conn, msg_dict)

        msg = _receive_message(self.dsmq_conn)
        if msg is None:
            raise RuntimeError("Connection terminated by server")
        return msg["message"]

    def put(self, topic, msg_body):
        msg_dict = {"action": "put", "topic": topic, "message": msg_body}
        _send_message(self.dsmq_conn, msg_dict)


def _send_message(socket_conn, msg_dict):
    msg = json.dumps(msg_dict)
    msg_bytes = bytes(msg, "utf-8")
    n_bytes = len(msg_bytes)

    # Send a header first.
    # Add a large number to ensure that the message is the same size each time.
    header_dict = {"msg_length": n_bytes + _message_length_offset}
    header = json.dumps(header_dict)
    header_bytes = bytes(header, "utf-8")
    socket_conn.sendall(header_bytes)

    socket_conn.sendall(msg_bytes)


def _receive_message(socket_conn):
    # First receive a header
    header_data = socket_conn.recv(_header_length)
    if header_data is None:
        return None
    if len(header_data) == 0:
        return None

    header_str = header_data.decode("utf-8")
    header = json.loads(header_str)
    msg_length = header["msg_length"] - _message_length_offset

    data = socket_conn.recv(msg_length)
    if data is None:
        return None
    if len(data) == 0:
        return None

    msg_str = data.decode("utf-8")
    msg = json.loads(msg_str)
    return msg


def _handle_client_connection(socket_conn):
    sqlite_conn = sqlite3.connect("file:mem1?mode=memory&cache=shared")
    cursor = sqlite_conn.cursor()

    client_creation_time = time.time()
    last_read_times = {}
    time_of_last_purge = time.time()

    while True:
        msg = _receive_message(socket_conn)
        if msg is None:
            break

        topic = msg["topic"]
        timestamp = time.time()

        if msg["action"] == "put":
            msg["timestamp"] = timestamp

            # This block allows for multiple retries if the database
            # is busy.
            for i_retry in range(_n_retries):
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
                    wait_time = _first_retry * 2**i_retry
                    time.sleep(wait_time)
                    continue
                break

        elif msg["action"] == "get":
            try:
                last_read_time = last_read_times[topic]
            except KeyError:
                last_read_times[topic] = client_creation_time
                last_read_time = last_read_times[topic]
            msg["last_read_time"] = last_read_time

            # This block allows for multiple retries if the database
            # is busy.
            for i_retry in range(_n_retries):
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
                    wait_time = _first_retry * 2**i_retry
                    time.sleep(wait_time)
                    continue
                break

            try:
                result = cursor.fetchall()[0]
                message = result[0]
                timestamp = result[1]
                last_read_times[topic] = timestamp
            except IndexError:
                # Handle the case where no results are returned
                message = ""

            _send_message(socket_conn, {"message": message})
        else:
            print("Action must either be 'put' or 'get'")

        # Periodically clean out messages from the queue that are
        # past their sell buy date.
        # This operation is pretty fast. I clock it at 12 us on my machine.
        if time.time() - time_of_last_purge > _time_to_live:
            cursor.execute(
                """
DELETE FROM messages
WHERE timestamp < :time_threshold
                """,
                {"time_threshold": time_of_last_purge}
            )
            sqlite_conn.commit()
            time_of_last_purge = time.time()

    sqlite_conn.close()


if __name__ == "__main__":
    if len(sys.argv) == 3:
        host = sys.argv[1]
        port = int(sys.argv[2])
        start_server(host=host, port=port)
    elif len(sys.argv) == 2:
        host = sys.argv[1]
        start_server(host=host)
    elif len(sys.argv) == 1:
        start_server()
    else:
        print(
            """
Try one of these:
$ python3 dsmq.py

$ python3 dsmq.py 127.0.0.1

$ python3 dsmq.py 127.0.0.1 25853

            """
        )
