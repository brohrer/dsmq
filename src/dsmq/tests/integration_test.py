import multiprocessing as mp
import time
from dsmq.server import serve
from dsmq.client import connect

# spawn is the default method on macOS
# mp.set_start_method('spawn')

host = "127.0.0.1"
port = 30303

_short_pause = 0.001
_pause = 0.01
_long_pause = 0.1
_very_long_pause = 2.0


def test_client_server():
    p_server = mp.Process(target=serve, args=(host, port))
    p_server.start()
    mq = connect(host, port)
    read_completes = False
    write_completes = False

    n_iter = 11
    for i in range(n_iter):
        mq.put("test", f"msg_{i}")
        write_completes = True

    for i in range(n_iter):
        msg = mq.get("test")
        read_completes = True

    assert msg
    assert write_completes
    assert read_completes

    mq.shutdown_server()
    mq.close()

    closed = False
    try:
        mq = connect(host, port)
    except ConnectionRefusedError as e:
        print(e)
        closed = True
    assert closed


def test_write_one_read_one():
    p_server = mp.Process(target=serve, args=(host, port))
    p_server.start()
    write_client = connect(host, port)
    read_client = connect(host, port)

    write_client.put("test", "test_msg")

    # It takes a moment for the write to complete
    time.sleep(_pause)
    msg = read_client.get("test")

    assert msg == "test_msg"

    write_client.shutdown_server()
    write_client.close()
    read_client.close()


def test_get_wait():
    p_server = mp.Process(target=serve, args=(host, port))
    p_server.start()
    write_client = connect(host, port)
    read_client = connect(host, port)

    write_client.put("test", "test_msg")

    msg = read_client.get_wait("test")

    assert msg == "test_msg"

    write_client.shutdown_server()
    write_client.close()
    read_client.close()


def test_multitopics():
    p_server = mp.Process(target=serve, args=(host, port))
    p_server.start()
    write_client = connect(host, port)
    read_client = connect(host, port)

    write_client.put("test_A", "test_msg_A")
    write_client.put("test_B", "test_msg_B")

    msg_A = read_client.get_wait("test_A")
    msg_B = read_client.get_wait("test_B")

    assert msg_A == "test_msg_A"
    assert msg_B == "test_msg_B"

    write_client.shutdown_server()
    write_client.close()
    read_client.close()


def test_client_history_cutoff():
    p_server = mp.Process(target=serve, args=(host, port))
    p_server.start()
    write_client = connect(host, port)
    write_client.put("test", "test_msg")
    time.sleep(_pause)

    read_client = connect(host, port)
    msg = read_client.get("test")

    assert msg == ""

    write_client.shutdown_server()
    write_client.close()
    read_client.close()


def test_two_write_clients():
    p_server = mp.Process(target=serve, args=(host, port))
    p_server.start()
    write_client_A = connect(host, port)
    write_client_B = connect(host, port)
    read_client = connect(host, port)

    write_client_A.put("test", "test_msg_A")
    # Wait briefly, to ensure the order of writes
    time.sleep(_pause)
    write_client_B.put("test", "test_msg_B")
    msg_A = read_client.get_wait("test")
    msg_B = read_client.get_wait("test")

    assert msg_A == "test_msg_A"
    assert msg_B == "test_msg_B"

    write_client_A.shutdown_server()
    write_client_A.close()
    write_client_B.close()
    read_client.close()


def test_two_read_clients():
    p_server = mp.Process(target=serve, args=(host, port))
    p_server.start()
    write_client = connect(host, port)
    read_client_A = connect(host, port)
    read_client_B = connect(host, port)

    write_client.put("test", "test_msg")
    msg_A = read_client_A.get_wait("test")
    msg_B = read_client_B.get_wait("test")

    assert msg_A == "test_msg"
    assert msg_B == "test_msg"

    write_client.shutdown_server()
    write_client.close()
    read_client_A.close()
    read_client_B.close()


def speed_write(stop_flag):
    fast_write_client = connect(host, port)
    while True:
        fast_write_client.put("speed_test", "speed")
        if stop_flag.is_set():
            break
    fast_write_client.close()


def test_speed_writing():
    p_server = mp.Process(target=serve, args=(host, port))
    p_server.start()
    write_client = connect(host, port)
    read_client = connect(host, port)

    stop_flag = mp.Event()
    p_speed_write = mp.Process(target=speed_write, args=(stop_flag,))
    p_speed_write.start()
    time.sleep(_pause)

    # time_a = time.time()
    write_client.put("test", "test_msg")
    # time_b = time.time()
    msg = read_client.get_wait("test")
    # time_c = time.time()

    # write_time = int((time_b - time_a) * 1e6)
    # read_time = int((time_c - time_b) * 1e6)
    # print(f"write time: {write_time} us,  read time: {read_time} us")

    assert msg == "test_msg"

    stop_flag.set()
    p_speed_write.join()
    read_client.close()
    write_client.shutdown_server()
    write_client.close()


def speed_read(stop_flag):
    fast_read_client = connect(host, port)
    while True:
        fast_read_client.get("speed_test")
        if stop_flag.is_set():
            break
    fast_read_client.close()


def test_speed_reading():
    p_server = mp.Process(target=serve, args=(host, port))
    p_server.start()
    write_client = connect(host, port)
    read_client = connect(host, port)

    stop_flag = mp.Event()
    p_speed_read = mp.Process(target=speed_read, args=(stop_flag,))
    p_speed_read.start()

    # time_a = time.time()
    write_client.put("test", "test_msg")
    # time_b = time.time()
    msg = read_client.get_wait("test")
    # time_c = time.time()

    # write_time = int((time_b - time_a) * 1e6)
    # read_time = int((time_c - time_b) * 1e6)
    # print(f"write time: {write_time} us,  read time: {read_time} us")

    assert msg == "test_msg"

    stop_flag.set()
    p_speed_read.join()
    p_speed_read.kill()
    read_client.close()
    write_client.shutdown_server()
    # time.sleep(_pause)
    write_client.close()
