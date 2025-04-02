import time

timeout = 0  # seconds to wait
current_time = 0


def print_start(section: str) -> None:
    global current_time
    current_time = time.time()
    print(section.ljust(50), end="\t")


def print_end() -> None:
    print(f"{time.time() - current_time:.2f}s")
    time.sleep(timeout)
