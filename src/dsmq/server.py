import json
import os
import sqlite3
import sys
from threading import Thread
import time
from websockets.sync.server import serve as ws_serve
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

_default_host = "127.0.0.1"
_default_port = 30008
_n_retries = 20
_first_retry = 0.005  # seconds
_time_between_cleanup = 0.05  # seconds
_max_queue_length = 10

# Make this global so it's easy to share
dsmq_server = None


def serve(
    host=_default_host,
    port=_default_port,
    name="mqdb",
    verbose=False,
):
    """
    For best results, start this running in its own process and walk away.
    """
    # May occasionally create files with this name.
    # https://sqlite.org/inmemorydb.html
    # "...parts of a temporary database might be flushed to disk if the
    # database becomes large or if SQLite comes under memory pressure."
    global _db_name
    _db_name = f"file:{name}?mode=memory&cache=shared"

    cleanup_temp_files()
    sqlite_conn = sqlite3.connect(_db_name)
    cursor = sqlite_conn.cursor()

    # Tweak the connection to make it faster
    # and keep long-term latency more predictable.
    # These also make it more susceptible to corruption during shutdown,
    # but since dsmq is meant to be ephemeral, that's not a concern.
    cursor.execute("PRAGMA journal_mode = OFF")
    cursor.execute("PRAGMA synchronous = OFF")
    cursor.execute("PRAGMA secure_delete = OFF")
    cursor.execute("PRAGMA temp_store = MEMORY")

    cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (timestamp DOUBLE, topic TEXT, message TEXT)
    """)

    # Making this global in scope is a way to make it available
    # to the shutdown operation. It's an awkward construction,
    # and a method of last resort.
    global dsmq_server

    for i_retry in range(_n_retries):
        try:
            with ws_serve(request_handler, host, port) as dsmq_server:
                dsmq_server.serve_forever()

            if verbose:
                print()
                print(f"Server started at {host} on port {port}.")
                print("Waiting for clients...")

            break

        except OSError:
            # Catch the case where the address is already in use
            if verbose:
                print()
                if i_retry < _n_retries - 1:
                    print(f"Couldn't start dsmq server on {host} on port {port}.")
                    print(f"    Trying again ({i_retry}) ...")
                else:
                    print()
                    print(f"Failed to start dsmq server on {host} on port {port}.")
                    print()
                    raise

            wait_time = _first_retry * 2**i_retry
            time.sleep(wait_time)

    sqlite_conn.close()
    time.sleep(_time_between_cleanup)
    cleanup_temp_files()


def cleanup_temp_files():
    # Under some condition
    # (which I haven't yet been able to pin down)
    # a file is generated with the db name.
    # If it is not removed, it gets
    # treated as a SQLite db on disk,
    # which dramatically slows it down,
    # especially the way it's used here for
    # rapid-fire one-item reads and writes.
    global _db_name
    filenames = os.listdir()
    for filename in filenames:
        if filename[: len(_db_name)] == _db_name:
            try:
                os.remove(filename)
            except FileNotFoundError:
                pass


def request_handler(websocket):
    global _db_name
    sqlite_conn = sqlite3.connect(_db_name)
    cursor = sqlite_conn.cursor()

    client_creation_time = time.time()
    last_read_times = {}
    time_of_last_purge = time.time()

    try:
        for msg_text in websocket:
            msg = json.loads(msg_text)
            topic = msg["topic"]
            timestamp = time.time()

            if msg["action"] == "put":
                msg["timestamp"] = timestamp

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
                    pass

            elif msg["action"] == "get":
                try:
                    last_read_time = last_read_times[topic]
                except KeyError:
                    last_read_times[topic] = client_creation_time
                    last_read_time = last_read_times[topic]
                msg["last_read_time"] = last_read_time

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
                    pass

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

                def shutdown_gracefully(server_to_shutdown):
                    server_to_shutdown.shutdown()
                    # cleanup_temp_files()

                Thread(target=shutdown_gracefully, args=(dsmq_server,)).start()
                break
            else:
                raise RuntimeWarning(
                    "dsmq client action must either be 'put', 'get', or 'shutdown'"
                )

            # Periodically clean out messages to keep individual queues at
            # a manageable length and the overall mq small.
            if time.time() - time_of_last_purge > _time_between_cleanup:
                try:
                    cursor.execute(
                        """
                        DELETE
                        FROM messages
                        WHERE topic = :topic
                        AND timestamp IN (
                          SELECT timestamp
                          FROM (
                              SELECT timestamp,
                              RANK() OVER (ORDER BY timestamp DESC) recency_rank
                              FROM messages
                              WHERE topic = :topic
                          )
                          WHERE recency_rank >= :max_queue_length
                        )
                        """,
                        {
                            "max_queue_length": _max_queue_length,
                            "topic": topic,
                        },
                    )
                    sqlite_conn.commit()
                    time_of_last_purge = time.time()
                except sqlite3.OperationalError:
                    # Database may be locked. Try again next time.
                    pass

    except (ConnectionClosedError, ConnectionClosedOK):
        # Something happened on the other end and this handler
        # is no longer needed.
        pass

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
