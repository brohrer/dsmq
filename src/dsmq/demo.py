import multiprocessing as mp

# spawn is the default method on macOS,
# starting in Python 3.14 it will be the default in Linux too.
try:
    mp.set_start_method('spawn')
except RuntimeError:
    # Will throw an error if the start method has alraedy been set.
    pass

from dsmq.server import serve  # noqa: E402
import dsmq.example_get_client  # noqa: E402
import dsmq.example_put_client  # noqa: E402

HOST = "127.0.0.1"
PORT = 25252


def test_server_with_clients():
    p_server = mp.Process(target=serve, args=(HOST, PORT))
    p_server.start()

    p_putter = mp.Process(target=dsmq.example_put_client.run, args=(HOST, PORT, 20))
    p_getter = mp.Process(target=dsmq.example_get_client.run, args=(HOST, PORT, 20))

    p_putter.start()
    p_getter.start()


if __name__ == "__main__":
    test_server_with_clients()
