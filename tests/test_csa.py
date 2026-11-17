import random

import pytest

from src.budget import Budget
from src.csa import (
    MUTMAX, Cell, clone_priority, csa_f, csa_t, distance, ext_insert, ext_swap, fitness, grasp, int_swap,
    random_ext_insert, random_ext_swap, rcl_size, receptor_editing, reselect, vnd,
)
from src.h5 import h5
from src.instance import Instance, list_instances, load_instance
from src.schedule import Schedule, validate
from tests.helpers import brute_force_optimum, hard_instance, hard_instances, tiny_instance


def plain(p, d):
    """준비시간이 없고 모든 작업이 모든 기계에 적격인 인스턴스."""
    m, n = len(p), len(d)
    zero = [[[0] * n for _ in range(n)] for _ in range(m)]
    return Instance("plain", n, m, p, zero, d, [[True] * n for _ in range(m)])


def sample_instances():
    regular = [load_instance(p) for p in list_instances("small")[::960] + list_instances("medium")[::1440]]
    return regular + hard_instances()


# ---- 이웃 연산자 ----

def test_internal_swap_applies_the_best_improving_swap():
    inst = plain([[1, 2, 3]], [6, 3, 1])
    sched = Schedule.from_seqs(inst, [[0, 1, 2]])  # 지연 5
    assert int_swap(inst, sched, random.Random(0)) is True
    assert (sched.seqs, sched.total) == ([[2, 1, 0]], 4)


def test_internal_swap_leaves_a_local_optimum_untouched():
    inst = plain([[1, 2, 3]], [1, 3, 6])
    sched = Schedule.from_seqs(inst, [[0, 1, 2]])
    assert int_swap(inst, sched, random.Random(0)) is False
    assert sched.seqs == [[0, 1, 2]]


def test_external_insertion_moves_a_job_off_the_most_tardy_machine():
    inst = plain([[1, 1], [1, 1]], [1, 1])
    sched = Schedule.from_seqs(inst, [[0, 1], []])  # 작업 1이 1만큼 지연
    assert ext_insert(inst, sched, random.Random(0)) is True
    assert (sched.seqs, sched.total) == ([[1], [0]], 0)
    assert validate(inst, sched) == []


def test_external_insertion_respects_eligibility():
    inst = plain([[1, 1], [1, 1]], [1, 1])
    inst.ok[1] = [False, False]
    sched = Schedule.from_seqs(inst, [[0, 1], []])
    assert ext_insert(inst, sched, random.Random(0)) is False
    assert sched.seqs == [[0, 1], []]


def test_external_insertion_does_not_apply_a_worsening_move():
    inst = plain([[1, 1], [9, 9]], [1, 1])
    sched = Schedule.from_seqs(inst, [[0, 1], []])  # 기계 1로 옮기면 지연이 1에서 8로 늘어난다
    assert ext_insert(inst, sched, random.Random(0)) is False
    assert sched.total == 1


def test_external_swap_exchanges_jobs_between_machines():
    inst = plain([[5, 1], [1, 5]], [1, 1])
    sched = Schedule.from_seqs(inst, [[0], [1]])  # 지연 4 + 4
    assert ext_swap(inst, sched, random.Random(0)) is True
    assert (sched.seqs, sched.total) == ([[1], [0]], 0)


def test_vnd_stops_at_a_solution_no_operator_can_improve():
    rng = random.Random(3)
    for inst in sample_instances():
        sched = grasp(inst, rng)
        vnd(inst, sched, rng)
        assert validate(inst, sched) == [], inst.name
        assert not any(op(inst, sched, rng) for op in (int_swap, ext_insert, ext_swap)), inst.name


# ---- 수용체 편집: 수락 검사가 없는 무작위 이동 (Diana et al., 2015, 3.3.1절) ----

def test_random_external_insertion_is_applied_even_when_it_worsens_the_schedule():
    inst = plain([[1, 1], [9, 9]], [1, 1])
    sched = Schedule.from_seqs(inst, [[0, 1], []])  # 총 지연 1. 어느 작업을 기계 1로 옮겨도 8이 된다
    assert random_ext_insert(inst, sched, random.Random(0)) is True
    assert (sched.total, len(sched.seqs[1])) == (8, 1)
    assert validate(inst, sched) == []


def test_random_external_insertion_needs_another_eligible_machine():
    zero = [[[0, 0], [0, 0]], [[0, 0], [0, 0]]]
    inst = Instance("fixed", 2, 2, [[1, 1], [1, 1]], zero, [1, 1], [[True, True], [False, False]])
    sched = Schedule.from_seqs(inst, [[0, 1], []])
    assert random_ext_insert(inst, sched, random.Random(0)) is False
    assert sched.seqs == [[0, 1], []]


def test_random_external_swap_exchanges_two_jobs_on_different_machines():
    inst = plain([[5, 1], [1, 5]], [1, 1])
    sched = Schedule.from_seqs(inst, [[0], [1]])
    assert random_ext_swap(inst, sched, random.Random(0)) is True
    assert (sched.seqs, sched.total) == ([[1], [0]], 0)


def test_random_moves_keep_benchmark_schedules_valid():
    rng = random.Random(11)
    for inst in sample_instances():
        sched = grasp(inst, rng)
        for _ in range(200):
            random_ext_insert(inst, sched, rng)
            random_ext_swap(inst, sched, rng)
        assert validate(inst, sched) == [], inst.name


def test_receptor_editing_perturbs_a_local_optimum():
    rng = random.Random(12)
    inst = hard_instance(6)
    sched = grasp(inst, rng)
    vnd(inst, sched, rng)
    before = {j: i for i, seq in enumerate(sched.seqs) for j in seq}
    receptor_editing(inst, sched, rng)
    moved = sum(1 for i, seq in enumerate(sched.seqs) for j in seq if before[j] != i)
    assert 1 <= moved <= MUTMAX  # 개선 여부와 무관하게 1회에서 MUTMAX회 사이의 이동이 적용된다
    assert validate(inst, sched) == []


# ---- 개체군 연산 ----

def test_rcl_size_reads_k_as_a_count_or_as_a_percentage():
    assert [rcl_size(remaining, percent=False) for remaining in (40, 5, 3)] == [5, 5, 3]
    assert [rcl_size(remaining, percent=True) for remaining in (40, 21, 20, 1)] == [2, 2, 1, 1]


def test_grasp_is_a_deterministic_greedy_construction_when_the_list_holds_one_job():
    inst = hard_instance(0)  # n = 6이므로 5% 목록에는 항상 작업이 하나만 들어간다
    schedules = {str(grasp(inst, random.Random(seed)).seqs) for seed in range(5)}
    assert len(schedules) == 1


def test_clone_priority_resets_only_after_an_improvement():
    assert clone_priority(60, improved=True) == 100
    assert clone_priority(60, improved=False) == 55
    assert clone_priority(3, improved=False) == 0


def test_grasp_builds_valid_schedules():
    rng = random.Random(4)
    for inst in sample_instances():
        assert validate(inst, grasp(inst, rng)) == [], inst.name


def test_distance_counts_jobs_whose_predecessor_differs():
    inst = tiny_instance()
    a = Cell(Schedule.from_seqs(inst, [[0, 2], [3, 1]]))
    b = Cell(Schedule.from_seqs(inst, [[2, 0], [3, 1]]))
    c = Cell(Schedule.from_seqs(inst, [[0, 2], [1, 3]]))
    assert distance(a, a) == 0
    assert distance(a, b) == 2  # 작업 0과 작업 2의 직전 작업이 다르다
    assert distance(b, c) == 4


def test_fitness_averages_rank_score_and_priority():
    inst = tiny_instance()
    cells = [Cell(Schedule.from_seqs(inst, [[0, 2], [3, 1]])) for _ in range(3)]
    for cell, total in zip(cells, [10, 20, 30]):
        cell.sched.total = total
    assert fitness(cells) == pytest.approx([9 / 24, 8 / 24, 7 / 24])
    cells[1].prio = cells[2].prio = 0
    assert fitness(cells) == pytest.approx([17 / 24, 4 / 24, 3 / 24])
    cells[0].prio = 0  # 우선도의 합이 0이면 우선도 항을 균등하게 준다
    assert fitness(cells) == pytest.approx([9 / 24, 8 / 24, 7 / 24])


def test_reselect_keeps_the_best_and_then_prefers_distant_solutions():
    inst = tiny_instance()
    best = Cell(Schedule.from_seqs(inst, [[0, 2], [3, 1]]))
    near = Cell(Schedule.from_seqs(inst, [[2, 0], [3, 1]]))  # best와의 거리 2
    far = Cell(Schedule.from_seqs(inst, [[2, 0], [1, 3]]))  # best와의 거리 4
    near.sched.total, far.sched.total = 3, 4
    rng = random.Random(0)
    assert reselect([far, near, best], rng, size=2, x=2) == [best, far]  # 후보 2개 중 더 먼 해를 고른다
    assert reselect([far, near, best], rng, size=2, x=1) == [best, near]  # 후보 목록에는 near만 들어간다
    assert reselect([far, near, best], rng, size=5, x=4) == [best, far, near]


def test_reselect_does_not_allow_repeated_solutions():
    inst = tiny_instance()
    best = Cell(Schedule.from_seqs(inst, [[0, 2], [3, 1]]))
    twin = Cell(Schedule.from_seqs(inst, [[0, 2], [3, 1]]))
    far = Cell(Schedule.from_seqs(inst, [[2, 0], [1, 3]]))
    assert reselect([best, twin, far], random.Random(0), size=3, x=4) == [best, far]


def test_reselect_breaks_ties_in_the_objective_at_random():
    inst = tiny_instance()
    one = Cell(Schedule.from_seqs(inst, [[2, 0], [3, 1]]))
    other = Cell(Schedule.from_seqs(inst, [[2, 0], [1, 3]]))  # 두 해의 총 지연은 모두 3이다
    firsts = {id(reselect([one, other], random.Random(seed), size=1, x=4)[0]) for seed in range(20)}
    assert len(firsts) == 2


# ---- 알고리즘 전체 ----

def test_csa_returns_a_valid_schedule_with_matching_objective():
    for inst in sample_instances():
        for algo in (csa_f, csa_t):
            result = algo(inst, random.Random(5), Budget(max_iters=3))
            assert validate(inst, result.schedule) == [], inst.name
            assert result.objective == result.schedule.total


def test_csa_t_is_never_worse_than_h5():
    for inst in sample_instances():
        assert csa_t(inst, random.Random(6), Budget(max_iters=2)).objective <= h5(inst).total, inst.name


def test_same_seed_gives_the_same_result_in_iteration_mode():
    inst = hard_instance(5)
    first = csa_f(inst, random.Random(7), Budget(max_iters=3))
    second = csa_f(inst, random.Random(7), Budget(max_iters=3))
    assert first.objective > 0
    assert first.schedule.seqs == second.schedule.seqs


def test_best_value_never_increases_over_generations():
    for inst in hard_instances():
        trace = csa_f(inst, random.Random(8), Budget(max_iters=5)).info["trace"]
        assert trace == sorted(trace, reverse=True), inst.name


def test_csa_is_never_better_than_the_optimum():
    for inst in hard_instances()[:2]:  # n = 6
        assert csa_t(inst, random.Random(9), Budget(max_iters=5)).objective >= brute_force_optimum(inst), inst.name


def test_csa_runs_every_requested_generation_unless_it_reaches_zero():
    # 수용체 편집이 무작위 이동이므로 탐색이 스스로 멈추지 않는다. 종료 조건은 실행 예산과 총 지연 0뿐이다
    inst = hard_instance(0)  # 최적 총 지연이 0보다 크다
    result = csa_f(inst, random.Random(10), Budget(max_iters=30))
    assert result.objective > 0
    assert result.iterations == 30
    assert len(result.info["trace"]) == 31


def test_csa_accepts_the_count_reading_of_the_candidate_list():
    for inst in hard_instances()[:4]:
        result = csa_t(inst, random.Random(13), Budget(max_iters=3), rcl_percent=False)
        assert validate(inst, result.schedule) == [], inst.name
        assert result.objective <= h5(inst).total
