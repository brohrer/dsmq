import multiprocessing as mp
import time

from dsmq.server import serve
from dsmq.client import connect

host = "127.0.0.1"
port = 30303
verbose = False

_pause = 0.01
_very_long_pause = 1.0

_n_iter = int(1e3)
_n_long_char = int(1e4)

_short_msg = "q"
_long_msg = str(["q"] * _n_long_char)

_test_topic = "test"


def main():
    print()
    print("dsmq timing measurements")

    time_short_writes()
    time_long_writes()
    time_empty_reads()
    time_short_reads()
    time_long_reads()


def time_short_writes():
    condition = "short write"

    duration, duration_close = time_writes(msg=_short_msg, n_iter=1)

    print()
    print(f"Time for first {condition}  [including closing]")
    print(f"        {int(duration)} μs  [{int(duration_close)} μs]")

    avg_duration, avg_duration_close = time_writes(msg=_short_msg, n_iter=_n_iter)

    print(f"Average time for a {condition}  [including closing]")
    print(f"        {int(avg_duration)} μs  [{int(avg_duration_close)} μs]")


def time_long_writes():
    duration, duration_close = time_writes(msg=_long_msg, n_iter=1)

    condition = "long write"
    print()
    print(f"Time for first {condition}  [including closing]")
    print(f"        {int(duration)} μs  [{int(duration_close)} μs]")

    avg_duration, avg_duration_close = time_writes(msg=_long_msg, n_iter=_n_iter)

    condition = f"long write ({_n_long_char} characters)"
    print(f"Average time for a {condition}  [including closing]")
    print(f"        {int(avg_duration)} μs  [{int(avg_duration_close)} μs]")

    condition = "long write (per 1000 characters)"
    print(f"Average time for a {condition}  [including closing]")
    print(
        f"        {int(1000 * avg_duration / _n_long_char)} μs  "
        + f"[{int(1000 * avg_duration_close / _n_long_char)}] μs"
    )


def time_writes(msg="message", n_iter=1):
    p_server = mp.Process(target=serve, args=(host, port, verbose))
    p_server.start()
    time.sleep(_pause)
    write_client = connect(host, port)

    start_time = time.time()
    for _ in range(n_iter):
        write_client.put(_test_topic, msg)
    avg_duration = 1e6 * (time.time() - start_time) / n_iter  # microseconds

    write_client.shutdown_server()
    write_client.close()

    p_server.join(_very_long_pause)
    if p_server.is_alive():
        print("    Doing a hard shutdown on mq server")
        p_server.kill()
    avg_duration_close = 1e6 * (time.time() - start_time) / n_iter  # microseconds

    return avg_duration, avg_duration_close


def time_empty_reads():
    condition = "empty read"

    duration, duration_close = time_reads(msg=None, n_iter=1)

    print()
    print(f"Time for first {condition}  [including closing]")
    print(f"        {int(duration)} μs  [{int(duration_close)} μs]")

    avg_duration, avg_duration_close = time_reads(msg=None, n_iter=_n_iter)

    print(f"Average time for a {condition}  [including closing]")
    print(f"        {int(avg_duration)} μs  [{int(avg_duration_close)} μs]")


def time_short_reads():
    condition = "short read"

    duration, duration_close = time_reads(msg=_short_msg, n_iter=1)

    print()
    print(f"Time for first {condition}  [including closing]")
    print(f"        {int(duration)} μs  [{int(duration_close)} μs]")

    avg_duration, avg_duration_close = time_reads(msg=_short_msg, n_iter=_n_iter)

    print(f"Average time for a {condition}  [including closing]")
    print(f"        {int(avg_duration)} μs  [{int(avg_duration_close)} μs]")


def time_long_reads():
    condition = f"long read ({_n_long_char} characters)"

    duration, duration_close = time_reads(msg=_long_msg, n_iter=1)

    print()
    print(f"Time for first {condition}  [including closing]")
    print(f"        {int(duration)} μs  [{int(duration_close)} μs]")

    avg_duration, avg_duration_close = time_reads(msg=_long_msg, n_iter=_n_iter)

    print(f"Average time for a {condition}  [including closing]")
    print(f"        {int(avg_duration)} μs  [{int(avg_duration_close)} μs]")

    condition = "long read (per 1000 characters)"
    print(f"Average time for a {condition}  [including closing]")
    print(
        f"        {int(1000 * avg_duration / _n_long_char)} μs  "
        + f"[{int(1000 * avg_duration_close / _n_long_char)}] μs"
    )


def time_reads(msg=None, n_iter=1):
    p_server = mp.Process(target=serve, args=(host, port, verbose))
    p_server.start()
    time.sleep(_pause)
    # write_client = connect(host, port)
    read_client = connect(host, port)

    if msg is not None:
        for _ in range(n_iter):
            read_client.put(_test_topic, msg)

    start_time = time.time()
    for _ in range(n_iter):
        msg = read_client.get(_test_topic)

    avg_duration = 1e6 * (time.time() - start_time) / n_iter  # microseconds

    read_client.shutdown_server()
    # write_client.close()
    read_client.close()

    p_server.join(_very_long_pause)

    if p_server.is_alive():
        print("    Doing a hard shutdown on mq server")
        p_server.kill()

    avg_duration_close = 1e6 * (time.time() - start_time) / n_iter  # microseconds

    return avg_duration, avg_duration_close


if __name__ == "__main__":
    main()
