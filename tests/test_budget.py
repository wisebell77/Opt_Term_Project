import time

from src.budget import Budget, time_limit_seconds
from tests.helpers import tiny_instance


def test_time_limit_follows_the_paper_formula():
    inst = tiny_instance()  # n = 4, m = 2 -> 4 * 2 * 30 / 2 = 120 ms
    assert time_limit_seconds(inst) == 0.12
    assert time_limit_seconds(inst, scale=5) == 0.6


def test_iteration_budget_counts_ticks():
    budget = Budget(max_iters=4)
    budget.start()
    assert (budget.progress(), budget.done()) == (0.0, False)
    budget.tick()
    assert budget.progress() == 0.25
    budget.tick(3)
    assert (budget.iters, budget.done()) == (4, True)


def test_time_budget_expires():
    budget = Budget(time_limit=0.02)
    budget.start()
    assert not budget.done()
    time.sleep(0.03)
    assert budget.done()
    assert budget.progress() == 1.0  # 1을 넘지 않는다
