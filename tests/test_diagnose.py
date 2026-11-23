"""진단 스크립트(experiments/diagnose_csa.py, diagnose_sa.py)의 테스트."""
import random

import pytest

from experiments import diagnose_csa, diagnose_sa
from src.budget import Budget
from src.csa import Cell, csa_t
from src.schedule import Schedule, validate
from tests.helpers import hard_instance, tiny_instance


# ---- CSA의 다양성 ----

def test_observing_the_generations_does_not_change_the_search():
    inst = hard_instance(3)
    plain = csa_t(inst, random.Random(7), Budget(max_iters=4))
    seen = diagnose_csa.Diversity()
    watched = csa_t(inst, random.Random(7), Budget(max_iters=4), observe=seen)
    assert watched.schedule.seqs == plain.schedule.seqs and watched.iterations == plain.iterations == 4
    assert len(seen.rows) == 4  # 세대마다 한 번 기록한다
    for memory, clones, same, improved in seen.rows:
        assert 1 <= memory <= 20 and 1 <= clones <= 60 and 0 <= same <= 1 and 0 <= improved <= 1


def test_diversity_counts_distinct_solutions_and_unchanged_clones():
    inst = tiny_instance()
    good, poor = Schedule.from_seqs(inst, [[0, 2], [1, 3]]), Schedule.from_seqs(inst, [[2, 0], [1, 3]])
    assert (good.total, poor.total) == (2, 3)
    cells = [Cell(good), Cell(good.copy()), Cell(poor)]
    parents = [cells[0], cells[2], cells[2]]
    clones = [Cell(good.copy()), Cell(good.copy()), Cell(poor.copy())]  # 둘째 클론만 부모(poor)와 달라졌고 더 좋다
    seen = diagnose_csa.Diversity()
    seen(cells, parents, clones)
    assert seen.rows == [(2, 2, pytest.approx(2 / 3), pytest.approx(1 / 3))]
    assert seen.means() == [2, 2, pytest.approx(2 / 3), pytest.approx(1 / 3)]


def test_diversity_of_a_run_without_generations_is_empty():
    assert diagnose_csa.Diversity().means() == [0, 0, 0, 0]


def test_instances_are_split_by_whether_any_job_can_change_machines():
    inst = tiny_instance()  # 작업 0, 1은 두 기계 모두에서 처리할 수 있다
    assert diagnose_csa.movable(inst) is True
    inst.elig = [[0], [1], [0], [1]]
    assert diagnose_csa.movable(inst) is False


# ---- SA_t의 탐색 여유 ----

def test_neighbors_are_the_single_moves_of_sa():
    inst = tiny_instance()  # 작업 2는 기계 0, 작업 3은 기계 1에서만 처리할 수 있다
    seqs = [[0, 2], [1, 3]]
    found = list(diagnose_sa.neighbors(inst, seqs))
    # 내부 삽입 4가지, 외부 삽입 6가지(작업 0과 1을 상대 기계의 세 위치로), 외부 교환 1가지(작업 0과 1)
    assert len(found) == 4 + 6 + 1
    for changes in found:
        moved = [seq[:] for seq in seqs]
        for i, seq in changes:
            moved[i] = seq
        assert moved != seqs and validate(inst, Schedule.from_seqs(inst, moved)) == []


def test_distance_counts_the_moves_needed_to_reach_a_target_value():
    inst = tiny_instance()
    sched = Schedule.from_seqs(inst, [[2, 0], [1, 3]])  # 총 지연 3
    assert diagnose_sa.distance(inst, sched, 3) == 0
    assert diagnose_sa.distance(inst, sched, 2) == 1  # 기계 0의 순서를 바꾸면 2가 된다
    assert diagnose_sa.distance(inst, sched, -1) == 3  # 이동 2번으로 닿지 못하면 3(3번 이상)이다


def test_distance_finds_values_two_moves_away():
    inst = hard_instance(0)
    from src.h5 import h5

    sched = h5(inst)
    one = min(sum(diagnose_sa.costs_after(inst, sched, changes)) for changes in diagnose_sa.neighbors(inst, sched.seqs))
    two = one
    for changes in diagnose_sa.neighbors(inst, sched.seqs):
        seqs = [seq[:] for seq in sched.seqs]
        for i, seq in changes:
            seqs[i] = seq
        step = Schedule.from_seqs(inst, seqs)
        two = min(two, min(sum(diagnose_sa.costs_after(inst, step, more)) for more in diagnose_sa.neighbors(inst, seqs)))
    assert two < one < sched.total  # 이 인스턴스에서는 두 번 이동해야 닿는 더 좋은 값이 있다
    assert diagnose_sa.distance(inst, sched, one) == 1
    assert diagnose_sa.distance(inst, sched, two) == 2


def test_one_diagnostic_run_reports_when_the_optimum_was_found():
    name = "I_6_2_49_50_T04_R02_1"  # 최적값 53
    row = diagnose_sa.run((name, 53, "full", 1.0, 0))
    assert row[:7] == [name, 6, 2, "full", 1.0, 0, 53]
    start, objective, evals, found_at = row[7], row[8], row[9], row[10]
    assert objective == 53 <= start and 0 <= found_at <= evals
    descent = diagnose_sa.run((name, 53, "descent", 0.05, 0))
    assert descent[3] == "descent" and descent[8] >= 53
