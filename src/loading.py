from typing import Iterable
import time
from math import floor, ceil


def ft_progress(lst: Iterable[int]):
    start_time = time.time()
    bar_length = 10
    for i in lst:
        j = i + 1
        elapsed_time = time.time() - start_time
        arrival_time = (elapsed_time / j) * len(lst)

        proportion_to_conclude = j / len(lst)
        progress_bar = proportion_to_conclude * bar_length
        arrow_cell = ">" if progress_bar < bar_length else ""

        _bar = (
            "=" * floor(progress_bar),
            arrow_cell,
            " " * int(ceil((bar_length - progress_bar) - 1)),
        )
        bar = "".join(_bar)

        print(
            f"ETA: {arrival_time:.2f}s "
            f"[{proportion_to_conclude:4.0%}] "
            f"[{bar}] "
            f"{j}/{len(lst)} "
            " | "
            f"elapsed time {elapsed_time:.2f}s",
            end="\r",
        )
        yield i


# a_list = range(1000)
# ret = 0
# for elem in ft_progress(a_list):
#     ret += (elem + 3) % 5
#     time.sleep(0.01)
# print()
# print(ret)
