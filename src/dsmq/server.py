import json
import sqlite3
import sys
import time
from websockets.sync.server import serve as ws_serve

_default_host = "127.0.0.1"
_default_port = 30008
_n_retries = 5
_first_retry = 0.01  # seconds
_time_to_live = 600.0  # seconds


def serve(host=_default_host, port=_default_port):
    """
    For best results, start this running in its own process and walk away.
    """
    sqlite_conn = sqlite3.connect("file:mem1?mode=memory&cache=shared")
    cursor = sqlite_conn.cursor()
    cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (timestamp DOUBLE, topic TEXT, message TEXT)
    """)

    with ws_serve(request_handler, host, port) as server:
        server.serve_forever()
        print()
        print(f"Server started at {host} on port {port}.")
        print("Waiting for clients...")

    sqlite_conn.close()


def request_handler(websocket):
    sqlite_conn = sqlite3.connect("file:mem1?mode=memory&cache=shared")
    cursor = sqlite_conn.cursor()

    client_creation_time = time.time()
    last_read_times = {}
    time_of_last_purge = time.time()

    for msg_text in websocket:
        msg = json.loads(msg_text)
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

            websocket.send(json.dumps({"message": message}))
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
        serve(host=host, port=port)
    elif len(sys.argv) == 2:
        host = sys.argv[1]
        serve(host=host)
    elif len(sys.argv) == 1:
        serve()
    else:
        print(
            """
Try one of these:
$ python3 server.py

$ python3 server.py 127.0.0.1

$ python3 server.py 127.0.0.1 25853

"""
        )
