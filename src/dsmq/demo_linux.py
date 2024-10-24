# Heads up: This script only works on Linux because of use of "fork" method.
import multiprocessing as mp
import dsmq
import example_get_client
import example_put_client

mp.set_start_method("fork")

HOST = "127.0.0.1"
PORT = 25252


def test_server_with_clients():
    p_server = mp.Process(target=dsmq.start_server, args=(HOST, PORT))
    p_server.start()

    p_putter = mp.Process(target=example_put_client.run, args=(HOST, PORT, 20))
    p_getter = mp.Process(target=example_get_client.run, args=(HOST, PORT, 20))

    p_putter.start()
    p_getter.start()


if __name__ == "__main__":
    test_server_with_clients()
