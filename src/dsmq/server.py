import json
import os
import sqlite3
import sys
from threading import Thread
import time
from websockets.sync.server import serve as ws_serve

_default_host = "127.0.0.1"
_default_port = 30008
_n_retries = 5
_first_retry = 0.01  # seconds
_pause = 0.01  # seconds
_time_to_live = 600.0  # seconds

_db_name = "file::memory:?cache=shared"

# Make this global so it's easy to share
dsmq_server = None


def serve(host=_default_host, port=_default_port):
    """
    For best results, start this running in its own process and walk away.
    """
    # Cleanup temp files.
    # Under some condition
    # (which I haven't yet been able to pin down)
    # a file is generated with the db name.
    # If it is not removed, it gets
    # treated as a SQLite db on disk,
    # which dramatically slows it down,
    # especially the way it's used here for
    # rapid-fire one-item reads and writes.
    filenames = os.listdir()
    for filename in filenames:
        if filename[: len(_db_name)] == _db_name:
            os.remove(filename)

    sqlite_conn = sqlite3.connect(_db_name)
    cursor = sqlite_conn.cursor()
    cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (timestamp DOUBLE, topic TEXT, message TEXT)
    """)

    # Making this global in scope is a way to make it available
    # to the shutdown operation. It's an awkward construction,
    # and a method of last resort. (If you stumble across this and
    # figure out something more elegant, please submit a PR!
    # or send it to me at brohrer@gmail.com,
    global dsmq_server

    dsmq_server = ws_serve(request_handler, host, port)
    dsmq_server.serve_forever()
    print()
    print(f"Server started at {host} on port {port}.")
    print("Waiting for clients...")

    sqlite_conn.close()


def request_handler(websocket):
    sqlite_conn = sqlite3.connect(_db_name)
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
        elif msg["action"] == "shutdown":
            # Run this from a separate thread to prevent deadlock
            global dsmq_server
            print("Shutting down the dsmq server.")

            def shutdown_gracefully(server_to_shutdown):
                server_to_shutdown.shutdown()
                time.sleep(_pause)

                filenames = os.listdir()
                for filename in filenames:
                    if filename[: len(_db_name)] == _db_name:
                        try:
                            os.remove(filename)
                        except FileNotFoundError:
                            pass

            Thread(target=shutdown_gracefully, args=(dsmq_server,)).start()
            sqlite_conn.close()
        else:
            print("Action must either be 'put', 'get', or 'shudown'")

        # Periodically clean out messages from the queue that are
        # past their sell buy date.
        # This operation is pretty fast. I clock it at 12 us on my machine.
        if time.time() - time_of_last_purge > _time_to_live:
            cursor.execute(
                """
DELETE FROM messages
WHERE timestamp < :time_threshold
                """,
                {"time_threshold": time_of_last_purge},
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
