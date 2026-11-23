import math
import random

import pytest

from src.budget import Budget
from src.csa import grasp
from src.h5 import h5
from src.instance import Instance, list_instances, load_instance
from src.sa import fit_temperature, propose, sa_t, temperatures
from src.schedule import validate
from tests.helpers import hard_instance, hard_instances


# ---- 온도 설정과 냉각 ----

def test_fit_temperature_hits_the_target_acceptance_probability():
    assert fit_temperature([10], 0.80) == pytest.approx(-10 / math.log(0.80), rel=1e-6)
    assert fit_temperature([10], 0.01) == pytest.approx(-10 / math.log(0.01), rel=1e-6)
    deltas = [1, 5, 20, 80, 300]
    temp = fit_temperature(deltas, 0.5)
    assert sum(math.exp(-x / temp) for x in deltas) / len(deltas) == pytest.approx(0.5, rel=1e-6)


def test_geometric_and_log_cooling_run_from_t0_to_tf():
    for cooling in ("geo", "log"):
        temps = temperatures(50.0, 2.0, 100, cooling, n=40)
        assert len(temps) == 101
        assert temps[0] == pytest.approx(50.0) and temps[-1] == pytest.approx(2.0)
        assert all(a > b for a, b in zip(temps, temps[1:]))
    assert temperatures(50.0, 2.0, 100, "geo", n=40)[50] == pytest.approx(10.0)  # 기하 평균


def test_exponential_cooling_runs_from_t0_to_tf():
    for n in (6, 40):
        temps = temperatures(50.0, 2.0, 100, "exp", n=n)
        assert temps[0] == pytest.approx(50.0) and temps[-1] == pytest.approx(2.0)
        assert all(a > b for a, b in zip(temps, temps[1:]))
    # 작업 수가 많을수록 k^(1/n)이 느리게 늘어나므로, 첫 단계에서 더 많이 식는다
    assert temperatures(50.0, 2.0, 100, "exp", n=40)[1] < temperatures(50.0, 2.0, 100, "exp", n=6)[1]


def test_capped_exponential_cooling_stops_above_tf():
    # 계획서의 처음 설계: 냉각 계수를 0.9로 제한한다. ln(25) / 100^(1/40) > 0.9 이므로 종료 온도가 Tf보다 높게 남는다
    temps = temperatures(50.0, 2.0, 100, "exp_cap", n=40)
    assert temps[0] == pytest.approx(50.0)
    assert temps[-1] == pytest.approx(50.0 * math.exp(-0.9 * 100 ** (1 / 40)))
    assert temps[-1] > 2.0
    # 상한에 걸리지 않으면 Tf에 도달한다
    assert temperatures(50.0, 45.0, 100, "exp_cap", n=40)[-1] == pytest.approx(45.0)


def test_unknown_cooling_name_is_rejected():
    with pytest.raises(ValueError):
        temperatures(50.0, 2.0, 100, "linear", n=40)


# ---- 이웃 생성 ----

def test_incremental_cost_matches_full_recalculation_over_1000_random_moves():
    rng = random.Random(1)
    for inst in hard_instances():
        sched = grasp(inst, rng)
        where = [0] * inst.n
        for i, seq in enumerate(sched.seqs):
            for j in seq:
                where[j] = i
        for _ in range(1000):
            move = propose(inst, sched, where, rng)
            if move is None:
                continue
            _, changes, delta, relocations = move
            before = sched.total
            for i, seq, cost in changes:
                sched.set_machine(inst, i, seq, cost)
            for j, i in relocations:
                where[j] = i
            assert sched.total == before + delta
        assert validate(inst, sched) == [], inst.name  # 비용을 전부 다시 계산하여 대조한다
        assert all(j in sched.seqs[where[j]] for j in range(inst.n))


def test_all_three_move_kinds_are_generated():
    base = hard_instance(6)
    # 외부 교환이 가능하도록 모든 작업이 모든 기계에 적격인 인스턴스를 쓴다
    inst = Instance(base.name, base.n, base.m, base.p, base.s, base.d, [[True] * base.n for _ in range(base.m)])
    sched, rng = h5(inst), random.Random(2)
    where = [i for j in range(inst.n) for i, seq in enumerate(sched.seqs) if j in seq]
    kinds = {propose(inst, sched, where, rng)[0] for _ in range(300)}
    assert kinds == {"internal_insert", "external_insert", "external_swap"}


# ---- 알고리즘 전체 ----

def test_sa_returns_a_valid_schedule_no_worse_than_h5():
    for inst in hard_instances():
        for cooling in ("geo", "log", "exp", "exp_cap", "none"):
            result = sa_t(inst, random.Random(3), Budget(max_iters=3000), cooling)
            assert validate(inst, result.schedule) == [], inst.name
            assert result.objective == result.schedule.total <= h5(inst).total


def test_sa_improves_a_poor_starting_solution():
    inst = hard_instance(4)  # H5의 총 지연은 139이고, CSA는 15까지 줄인다
    assert sa_t(inst, random.Random(4), Budget(max_iters=30000)).objective < 139


def test_descent_mode_never_accepts_a_worsening_move():
    # cooling="none"은 진단용이다: 같은 이웃을 쓰되 나빠지는 이동을 받아들이지 않으므로, 현재 해가 곧 최선해이다
    inst = hard_instance(4)
    descent = sa_t(inst, random.Random(4), Budget(max_iters=3000), "none")
    assert descent.info["current"] == descent.objective < 139
    annealed = sa_t(inst, random.Random(4), Budget(max_iters=300), "geo")
    assert annealed.info["current"] > annealed.objective  # 온도가 높을 때에는 현재 해가 최선해보다 나빠져 있다


def test_same_seed_gives_the_same_result_in_iteration_mode():
    inst = hard_instance(5)
    first = sa_t(inst, random.Random(5), Budget(max_iters=5000))
    second = sa_t(inst, random.Random(5), Budget(max_iters=5000))
    assert first.schedule.seqs == second.schedule.seqs
    assert first.iterations == 5000


def test_sa_stops_immediately_when_h5_is_already_optimal():
    inst = load_instance(list_instances("medium")[1000])  # H5의 총 지연이 0이다
    result = sa_t(inst, random.Random(6), Budget(max_iters=5000))
    assert (result.objective, result.iterations) == (0, 0)


def test_sa_never_beats_the_optimum_and_records_temperatures():
    from tests.helpers import brute_force_optimum

    inst = hard_instance(0)
    result = sa_t(inst, random.Random(7), Budget(max_iters=20000))
    assert result.objective >= brute_force_optimum(inst)
    assert result.info["t0"] > result.info["tf"] > 0


def test_sa_returns_the_h5_solution_when_the_time_budget_is_already_spent():
    inst = hard_instance(4)
    result = sa_t(inst, random.Random(8), Budget(time_limit=1e-9))
    assert (result.objective, result.iterations) == (h5(inst).total, 0)
    assert result.info["t_end"] == result.info["t0"]
