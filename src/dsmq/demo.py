import multiprocessing as mp
from dsmq.server import serve
import dsmq.example_get_client
import dsmq.example_put_client

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
