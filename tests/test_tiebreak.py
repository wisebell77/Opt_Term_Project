"""동점 처리 기준(src/tiebreak.py)과, 기준에 따라 선택이 달라지는 지점의 테스트."""
import csv
import random

import pytest

from experiments import analyze_tiebreak, run
from experiments.run import METHODS, run_instance
from src import tiebreak
from src.budget import Budget
from src.csa import csa_f, csa_t, ext_insert, ext_swap, grasp, int_swap, worst_machine
from src.h5 import construct, h5
from src.insertion import best_position, best_position_total, insert
from src.instance import DATA_DIR, Instance, list_instances, load_instance
from src.schedule import Schedule, machine_cost, validate
from tests.helpers import HARD, hard_instances, tiny_instance
from tests.test_csa import plain
from tests.test_insertion import random_partial, sample_instances

MODES = ("first", "last", "csum", "random")


def allowed(candidates, mode):
    """기준 mode에서 선택될 수 있는 대상의 목록.

    candidates는 살펴보는 순서대로 나열한 (지연, 동점 비교에 쓰는 완료시간 합, 선택 대상)이다."""
    best = min((tard, csum) for tard, csum, _ in candidates)
    tied = [item for tard, csum, item in candidates if (tard, csum) == best]
    return {"first": tied[:1], "csum": tied[:1], "last": tied[-1:], "random": tied}[mode]


def position_candidates(inst, i, seq, j, mode):
    """작업 j를 기계 i의 각 위치에 넣은 결과. 선택 대상은 (지연 합, 완료시간 합, 위치)이다."""
    base = machine_cost(inst, i, seq)[0]
    out = []
    for pos in range(len(seq) + 1):
        tard, csum = machine_cost(inst, i, seq[:pos] + [j] + seq[pos:])
        # 논문의 규칙(삽입 전후 지연이 모두 0이면 완료시간 합으로 비교)은 모든 기준에서 유지된다
        out.append((tard, csum if mode == "csum" or tard == base == 0 else 0, (tard, csum, pos)))
    return out


def random_schedule(inst, rng):
    """모든 작업을 무작위 적격 기계의 무작위 위치에 넣은 해. 개선할 여지와 동점이 많다."""
    jobs = list(range(inst.n))
    rng.shuffle(jobs)
    seqs = [[] for _ in range(inst.m)]
    for j in jobs:
        seq = seqs[rng.choice(inst.elig[j])]
        seq.insert(rng.randint(0, len(seq)), j)
    return Schedule.from_seqs(inst, seqs)


def two_machines(p, d):
    zero = [[0, 0], [0, 0]]
    return Instance("two", 2, 2, p, [zero, zero], d, [[True, True], [True, True]])


# ---- 기준의 설정 ----

def test_the_default_policy_is_first_and_the_context_restores_it():
    assert tiebreak.mode == "first"
    with tiebreak.policy("last"):
        assert tiebreak.mode == "last"
        with tiebreak.policy("csum"):
            assert tiebreak.mode == "csum"
        assert tiebreak.mode == "last"
    assert tiebreak.mode == "first"


def test_the_policy_is_restored_after_an_error():
    with pytest.raises(RuntimeError):
        with tiebreak.policy("csum"):
            raise RuntimeError
    assert tiebreak.mode == "first"


def test_unknown_policies_and_random_without_a_generator_are_rejected():
    with pytest.raises(ValueError):
        with tiebreak.policy("middle"):
            pass
    with pytest.raises(ValueError):
        with tiebreak.policy("random"):
            pass
    assert tiebreak.mode == "first"


def test_rank_orders_tied_candidates_by_policy():
    assert tiebreak.rank(2, 5) == (2, 5)
    with tiebreak.policy("csum"):
        assert tiebreak.rank(2, 5) == (2, 5)
    with tiebreak.policy("last"):
        assert tiebreak.rank(2, 5) < tiebreak.rank(2, 4) < tiebreak.rank(1, 9)
    with tiebreak.policy("random", random.Random(0)):
        assert len({tiebreak.rank(2, 5) for _ in range(100)}) == 100  # 번호와 무관한 난수


def test_completion_time_is_compared_only_under_the_csum_policy():
    assert tiebreak.csum(7) == 0
    with tiebreak.policy("last"):
        assert tiebreak.csum(7) == 0
    with tiebreak.policy("csum"):
        assert tiebreak.csum(7) == 7


# ---- 삽입 연산 ----

@pytest.mark.parametrize("mode", MODES)
def test_best_position_follows_the_policy(mode):
    rng = random.Random(1)
    for inst in sample_instances():
        sched, rest = random_partial(inst, rng)
        for j in rest:
            for i in inst.elig[j]:
                seq = sched.seqs[i]
                with tiebreak.policy(mode, random.Random(3)):
                    got = best_position(inst, i, seq, j)
                assert got in allowed(position_candidates(inst, i, seq, j, mode), mode), (inst.name, i, j)


@pytest.mark.parametrize("mode", MODES)
def test_best_position_total_follows_the_policy(mode):
    rng = random.Random(2)
    for inst in sample_instances():
        sched, rest = random_partial(inst, rng)
        for j in rest:
            machines = []
            for i in inst.elig[j]:
                # 기계 안의 위치는 BestPosition의 규칙으로 정해진다
                options = allowed(position_candidates(inst, i, sched.seqs[i], j, mode), mode)
                tard, csum, _ = options[0]
                increase = csum - sched.csum[i] if mode == "csum" else 0
                machines.append((tard - sched.tard[i], increase, [(i, pos) for _, _, pos in options]))
            with tiebreak.policy(mode, random.Random(4)):
                got = best_position_total(inst, sched, j)
            assert got in [choice for group in allowed(machines, mode) for choice in group], (inst.name, j)


def test_positive_tardiness_ties_follow_the_policy():
    p, zero = [[5, 5, 1]], [[[0] * 3 for _ in range(3)]]
    inst = Instance("pos", 3, 1, p, zero, [1, 1, 1], [[True] * 3])
    # [0]에 작업 1을 넣는 두 위치는 지연 합도 완료시간 합도 같다
    assert best_position(inst, 0, [0], 1)[2] == 0
    with tiebreak.policy("last"):
        assert best_position(inst, 0, [0], 1)[2] == 1
    with tiebreak.policy("csum"):
        assert best_position(inst, 0, [0], 1)[2] == 0
    with tiebreak.policy("random", random.Random(0)):
        assert {best_position(inst, 0, [0], 1)[2] for _ in range(50)} == {0, 1}


def test_positive_tardiness_ties_with_different_completion_times_follow_the_policy():
    inst = plain([[1, 5, 4, 2]], [8, 4, 6, 6])
    # [0, 1, 2](지연 6)에 작업 3을 넣으면 위치 0, 1, 2의 지연 합이 모두 10이고 완료시간 합은 25, 24, 27이다
    assert best_position(inst, 0, [0, 1, 2], 3) == (10, 25, 0)
    with tiebreak.policy("last"):
        assert best_position(inst, 0, [0, 1, 2], 3) == (10, 27, 2)
    with tiebreak.policy("csum"):
        assert best_position(inst, 0, [0, 1, 2], 3) == (10, 24, 1)
    with tiebreak.policy("random", random.Random(0)):
        assert {best_position(inst, 0, [0, 1, 2], 3)[2] for _ in range(100)} == {0, 1, 2}


def test_the_zero_tardiness_rule_of_the_paper_holds_under_every_policy():
    inst = tiny_instance()
    # 기계 1에 작업 1을 넣는 두 위치 모두 지연이 0이고, 완료시간 합은 [1, 3]이 8, [3, 1]이 11이다
    for mode in MODES:
        with tiebreak.policy(mode, random.Random(0)):
            assert best_position(inst, 1, [3], 1) == (0, 8, 0), mode


def test_machine_ties_follow_the_policy():
    inst = two_machines([[1, 1], [1, 1]], [1, 1])
    empty = Schedule.empty(inst)
    assert best_position_total(inst, empty, 0) == (0, 0)
    with tiebreak.policy("last"):
        assert best_position_total(inst, empty, 0) == (1, 0)
    with tiebreak.policy("random", random.Random(0)):
        assert {best_position_total(inst, empty, 0) for _ in range(50)} == {(0, 0), (1, 0)}


def test_the_csum_policy_prefers_the_machine_that_finishes_earlier():
    # 작업 0은 기계 0에서 3, 기계 1에서 1이 걸리고, 납기가 넉넉하여 어느 기계에서도 지연이 없다
    inst = two_machines([[3, 3], [1, 1]], [9, 9])
    empty = Schedule.empty(inst)
    assert best_position_total(inst, empty, 0) == (0, 0)
    with tiebreak.policy("csum"):
        assert best_position_total(inst, empty, 0) == (1, 0)


# ---- H5 ----

def test_h5_places_tied_jobs_by_policy():
    inst = two_machines([[1, 1], [1, 1]], [1, 1])
    assert h5(inst).seqs == [[0], [1]]
    with tiebreak.policy("last"):
        assert h5(inst).seqs == [[1], [0]]


@pytest.mark.parametrize("mode", MODES)
def test_h5_returns_valid_schedules_under_every_policy(mode):
    for path in list_instances("small")[::160] + list_instances("medium")[::240]:
        inst = load_instance(path)
        with tiebreak.policy(mode, random.Random(1)):
            sched = h5(inst)
        assert validate(inst, sched) == [], (mode, inst.name)


def test_the_policy_changes_h5_on_benchmark_instances():
    totals = {mode: [] for mode in ("first", "last", "csum")}
    for path in list_instances("small")[::40]:
        inst = load_instance(path)
        for mode in totals:
            with tiebreak.policy(mode):
                totals[mode].append(h5(inst).total)
    assert totals["first"] != totals["last"]
    assert totals["first"] != totals["csum"]


# ---- 기준 first는 동점 기준을 도입하기 전의 동작과 같다 ----

# 도입 전의 코드로 얻은 해: (인스턴스 번호, H5, GRASP(시드 11), CSA_f(시드 7, 3세대), CSA_t(시드 7, 3세대))
LEGACY = [
    (0, [[3, 1], [5, 4, 0, 2]], [[3, 1], [5, 4, 0, 2]], [[3, 1], [0, 5, 2, 4]], [[3, 1], [0, 5, 2, 4]]),
    (
        3,
        [[0, 5, 13, 1], [8, 7, 14, 6, 11, 10, 2, 9, 4, 12, 3]],
        [[0, 5, 13, 1], [7, 14, 6, 8, 12, 4, 9, 11, 10, 2, 3]],
        [[0, 5, 13, 1], [2, 6, 7, 14, 12, 4, 9, 8, 10, 11, 3]],
        [[0, 5, 13, 1], [2, 6, 7, 14, 12, 4, 9, 8, 10, 11, 3]],
    ),
    (
        4,
        [[1, 14, 12, 8], [7, 2, 9, 5, 4, 10, 0, 13, 6, 11, 3]],
        [[14, 12, 8, 1], [13, 0, 6, 5, 11, 3, 2, 4, 9, 7, 10]],
        [[14, 12, 8, 1], [9, 0, 6, 10, 7, 2, 3, 5, 4, 11, 13]],
        [[14, 12, 8, 1], [9, 0, 6, 10, 7, 2, 3, 5, 4, 11, 13]],
    ),
    (
        6,
        [[7, 12, 4, 5, 17, 6, 8], [15, 14, 10, 3, 9], [19, 11, 0, 16, 2, 18], [1, 13]],
        [[17, 4, 6, 3, 12, 5, 9, 8, 7], [14, 10, 15], [2, 11, 0, 19, 16, 18], [1, 13]],
        [[7, 12, 4, 5, 17, 6, 8], [3, 14, 10, 15, 9], [19, 16, 2, 11, 0, 18], [1, 13]],
        [[7, 12, 4, 5, 17, 6, 8], [15, 14, 10, 3, 9], [19, 11, 0, 16, 2, 18], [1, 13]],
    ),
]


def test_the_first_policy_reproduces_the_results_before_policies_existed():
    instances = hard_instances()
    for index, h5_seqs, grasp_seqs, csa_f_seqs, csa_t_seqs in LEGACY:
        inst = instances[index]
        with tiebreak.policy("first"):
            assert h5(inst).seqs == h5_seqs, inst.name
            assert grasp(inst, random.Random(11)).seqs == grasp_seqs, inst.name
            assert csa_f(inst, random.Random(7), Budget(max_iters=3)).schedule.seqs == csa_f_seqs, inst.name
            assert csa_t(inst, random.Random(7), Budget(max_iters=3)).schedule.seqs == csa_t_seqs, inst.name


# ---- CSA ----

class Recorder:
    """GRASP가 제한 목록에서 고를 때 받은 목록을 기록하고 첫 후보를 고른다."""

    def __init__(self):
        self.lists = []
        self.source = random.Random(0)

    def choice(self, options):
        self.lists.append(list(options))
        return options[0]

    def random(self):
        return self.source.random()


def first_candidate_list(inst, mode, column=-3):
    """GRASP가 첫 작업을 고를 때의 제한 목록. 후보의 끝 세 값은 (작업, 기계, 위치)이며 기본으로 작업을 돌려준다."""
    recorder = Recorder()
    with tiebreak.policy(mode, recorder):
        grasp(inst, recorder)
    return [option[column] for option in recorder.lists[0]]


def test_grasp_fills_the_candidate_list_by_policy():
    # 기계가 1대이고 납기가 넉넉하여 어느 작업을 넣어도 지연이 없다. 가공시간은 작업 2, 4, 0, 6, 5의 순서로 짧다
    inst = plain([[3, 7, 1, 6, 2, 5, 4]], [100] * 7)
    assert first_candidate_list(inst, "first") == [0, 1, 2, 3, 4]
    assert first_candidate_list(inst, "last") == [6, 5, 4, 3, 2]
    assert first_candidate_list(inst, "csum") == [2, 4, 0, 6, 5]
    chosen = first_candidate_list(inst, "random")
    assert len(set(chosen)) == 5 and chosen not in ([0, 1, 2, 3, 4], [6, 5, 4, 3, 2], [2, 4, 0, 6, 5])


def test_grasp_picks_the_machine_of_each_candidate_by_policy():
    # 같은 기계 2대: 빈 해에서는 어느 기계에 넣어도 지연이 같다
    inst = two_machines([[1, 1], [1, 1]], [1, 1])
    assert first_candidate_list(inst, "first", column=-2) == [0, 0]
    assert first_candidate_list(inst, "last", column=-2) == [1, 1]
    # 작업 0은 기계 1에서 더 빨리 끝난다(지연은 어느 기계에서도 없다)
    inst = two_machines([[3, 3], [1, 1]], [9, 9])
    assert first_candidate_list(inst, "first", column=-2) == [0, 0]
    assert first_candidate_list(inst, "csum", column=-2) == [1, 1]


def after_move(operator, inst, seqs, mode, seed=0):
    """seqs에서 operator를 기준 mode로 한 번 적용한 뒤의 (기계별 순서, 총 지연)."""
    sched, rng = Schedule.from_seqs(inst, seqs), random.Random(seed)
    with tiebreak.policy(mode, rng):
        assert operator(inst, sched, rng) is True
    return sched.seqs, sched.total


def test_tied_internal_swaps_follow_the_policy():
    inst = plain([[3, 4, 3, 2]], [8, 7, 7, 8])
    # [0, 1, 2, 3]의 지연은 7이다. 지연을 6으로 줄이는 교환이 넷이고, 완료시간 합은 차례로 32, 29, 28, 31이다
    tied = [[[2, 1, 0, 3]], [[3, 1, 2, 0]], [[0, 3, 2, 1]], [[0, 1, 3, 2]]]
    assert after_move(int_swap, inst, [[0, 1, 2, 3]], "first") == (tied[0], 6)
    assert after_move(int_swap, inst, [[0, 1, 2, 3]], "last") == (tied[3], 6)
    assert after_move(int_swap, inst, [[0, 1, 2, 3]], "csum") == (tied[2], 6)
    results = [after_move(int_swap, inst, [[0, 1, 2, 3]], "random", seed)[0] for seed in range(100)]
    assert all(seqs in tied for seqs in results) and all(seqs in results for seqs in tied)


def test_tied_external_swaps_follow_the_policy():
    inst = plain([[1, 1, 3, 4], [2, 2, 4, 4]], [2, 5, 4, 2])
    # 기계 1([2, 3], 지연 6)의 작업을 기계 0([0, 1])의 작업과 바꾸어 총 지연을 4로 줄이는 교환이 셋이다.
    # 살펴보는 순서(기계 1의 위치, 기계 0의 위치)대로 완료시간 합은 15, 13, 16이다
    start = [[0, 1], [2, 3]]
    tied = [[[2, 1], [0, 3]], [[0, 2], [1, 3]], [[0, 3], [2, 1]]]
    assert after_move(ext_swap, inst, start, "first") == (tied[0], 4)
    assert after_move(ext_swap, inst, start, "last") == (tied[2], 4)
    assert after_move(ext_swap, inst, start, "csum") == (tied[1], 4)
    results = [after_move(ext_swap, inst, start, "random", seed)[0] for seed in range(100)]
    assert all(seqs in tied for seqs in results) and all(seqs in results for seqs in tied)


def test_tied_external_insertions_follow_the_policy():
    inst = plain([[2, 4, 1], [2, 4, 3]], [1, 6, 6])
    # 기계 0([0, 1, 2], 지연 2)의 어느 작업을 빈 기계 1로 옮겨도 총 지연은 1이고, 완료시간 합은 작업 0, 1, 2의 순서로 11, 9, 11이다
    start = [[0, 1, 2], []]
    tied = [[[1, 2], [0]], [[0, 2], [1]], [[0, 1], [2]]]
    assert after_move(ext_insert, inst, start, "first") == (tied[0], 1)
    assert after_move(ext_insert, inst, start, "last") == (tied[2], 1)
    assert after_move(ext_insert, inst, start, "csum") == (tied[1], 1)
    results = [after_move(ext_insert, inst, start, "random", seed)[0] for seed in range(100)]
    assert all(seqs in tied for seqs in results) and all(seqs in results for seqs in tied)


def starting_points():
    return [(inst, random_schedule(inst, random.Random(seed))) for inst in hard_instances() for seed in range(3)]


@pytest.mark.parametrize("mode", MODES)
def test_internal_swap_follows_the_policy(mode):
    checked = 0
    for inst, start in starting_points():
        i = worst_machine(start)
        seq = start.seqs[i]
        candidates = []
        for a in range(len(seq) - 1):
            for b in range(a + 1, len(seq)):
                swapped = seq[:]
                swapped[a], swapped[b] = swapped[b], swapped[a]
                tard, csum = machine_cost(inst, i, swapped)
                if tard < start.tard[i]:
                    candidates.append((tard, csum if mode == "csum" else 0, swapped))
        sched, rng = start.copy(), random.Random(6)
        with tiebreak.policy(mode, rng):
            moved = int_swap(inst, sched, rng)
        if candidates:
            checked += 1
            assert moved is True and sched.seqs[i] in allowed(candidates, mode), inst.name
        else:
            assert moved is False and sched.seqs == start.seqs, inst.name
    assert checked > 0


def machine_order(inst, i, seed):
    """이웃 연산자가 i 이외의 기계를 시도하는 순서(연산자는 같은 시드의 난수로 가장 먼저 이 순서를 정한다)."""
    others = [w for w in range(inst.m) if w != i]
    random.Random(seed).shuffle(others)
    return others


@pytest.mark.parametrize("mode", MODES)
def test_external_swap_follows_the_policy(mode):
    checked = 0
    for inst, start in starting_points():
        i = worst_machine(start)
        expected = None
        for w in machine_order(inst, i, 9):
            candidates = []
            for a, ja in enumerate(start.seqs[i]):
                for b, jb in enumerate(start.seqs[w]):
                    if inst.ok[w][ja] and inst.ok[i][jb]:
                        seq_i, seq_w = start.seqs[i][:], start.seqs[w][:]
                        seq_i[a], seq_w[b] = jb, ja
                        (tard_i, csum_i), (tard_w, csum_w) = machine_cost(inst, i, seq_i), machine_cost(inst, w, seq_w)
                        candidates.append((tard_i + tard_w, csum_i + csum_w if mode == "csum" else 0, (w, seq_i, seq_w)))
            if candidates and min(c[0] for c in candidates) < start.tard[i] + start.tard[w]:
                expected = allowed(candidates, mode)
                break
        sched, rng = start.copy(), random.Random(9)
        with tiebreak.policy(mode, rng):
            moved = ext_swap(inst, sched, rng)
        if expected:
            checked += 1
            w = expected[0][0]
            assert moved is True and (w, sched.seqs[i], sched.seqs[w]) in expected, inst.name
        else:
            assert moved is False and sched.seqs == start.seqs, inst.name
    assert checked > 0


@pytest.mark.parametrize("mode", MODES)
def test_external_insertion_follows_the_policy(mode):
    checked = 0
    for inst, start in starting_points():
        i = worst_machine(start)
        seq_i = start.seqs[i]
        expected = None
        for w in machine_order(inst, i, 9):
            seq_w = start.seqs[w]
            jobs = []
            for a, j in enumerate(seq_i):
                if not inst.ok[w][j]:
                    continue
                rest = seq_i[:a] + seq_i[a + 1 :]
                tard_i, csum_i = machine_cost(inst, i, rest)
                # 옮길 기계 안의 위치는 BestPosition의 규칙으로 정해진다
                options = allowed(position_candidates(inst, w, seq_w, j, mode), mode)
                tard_w, csum_w, _ = options[0]
                results = [(w, rest, seq_w[:pos] + [j] + seq_w[pos:]) for _, _, pos in options]
                jobs.append((tard_i + tard_w, csum_i + csum_w if mode == "csum" else 0, results))
            if jobs and min(c[0] for c in jobs) < start.tard[i] + start.tard[w]:
                expected = [result for group in allowed(jobs, mode) for result in group]
                break
        sched, rng = start.copy(), random.Random(9)
        with tiebreak.policy(mode, rng):
            moved = ext_insert(inst, sched, rng)
        if expected:
            checked += 1
            w = expected[0][0]
            assert moved is True and (w, sched.seqs[i], sched.seqs[w]) in expected, inst.name
        else:
            assert moved is False and sched.seqs == start.seqs, inst.name
    assert checked > 0


@pytest.mark.parametrize("mode", MODES)
def test_csa_returns_valid_schedules_under_every_policy(mode):
    for inst in hard_instances()[:4]:
        for algorithm in (csa_f, csa_t):
            rng = random.Random(7)
            with tiebreak.policy(mode, rng):
                result = algorithm(inst, rng, Budget(max_iters=3))
            assert validate(inst, result.schedule) == [], (mode, inst.name)
            assert result.objective == result.schedule.total


# ---- 실행기 ----

def test_the_runner_registers_h5_and_csa_under_every_policy():
    for base in ("h5", "csa_f", "csa_t"):
        for mode in ("last", "csum", "random"):
            assert f"{base}_{mode}" in METHODS
    # 무작위 기준에서는 H5의 결과도 실행마다 달라지므로 반복 실행한다
    assert METHODS["h5_last"][1] is False and METHODS["h5_csum"][1] is False and METHODS["h5_random"][1] is True
    assert len(run.TIE_METHODS) == 12 and set(run.TIE_METHODS) <= set(METHODS)


def test_the_runner_registers_sa_under_the_random_policy():
    for name in ("sa_geo_random", "sa_log_random", "sa_exp_random"):
        assert METHODS[name][1] is True
    assert not any(name.startswith("sa_") for name in run.TIE_METHODS)  # --methods tiebreak의 대상은 H5와 CSA뿐이다


def test_sa_under_the_random_policy_starts_from_the_h5_solution_of_that_policy():
    # SA_t에는 자체 동점 결정이 없고, 기준은 출발해인 H5에만 영향을 준다
    inst = load_instance(DATA_DIR / "small" / "I_6_4_49_50_T04_R02_7.txt")
    rng = random.Random(1)
    with tiebreak.policy("random", rng):
        start = h5(inst).total
    assert (h5(inst).total, start) == (19, 34)  # 이 시드에서는 기준 random의 H5가 기준 first의 H5와 다르다
    result = METHODS["sa_geo_random"][0](inst, random.Random(1), Budget(max_iters=50))
    assert result.info["trace"][0] == (0, start)
    assert validate(inst, result.schedule) == [] and result.objective <= start
    assert tiebreak.mode == "first"


def test_the_runner_applies_the_policy_and_restores_the_default():
    path = DATA_DIR / (HARD[3] + ".txt")
    inst = load_instance(path)
    rows = run_instance((str(path), ["h5", "h5_last", "h5_csum", "h5_random"], 2, 0.2, "test", set(), None))
    assert [(row["method"], row["rep"]) for row in rows] == [
        ("h5", 0), ("h5_last", 0), ("h5_csum", 0), ("h5_random", 0), ("h5_random", 1),
    ]
    by_method = {row["method"]: row["objective"] for row in rows}
    for mode in ("first", "last", "csum"):
        with tiebreak.policy(mode):
            expected = h5(inst).total
        assert by_method["h5" if mode == "first" else f"h5_{mode}"] == expected
    assert tiebreak.mode == "first"


def test_the_runner_writes_to_the_requested_file(tmp_path):
    out = tmp_path / "tiebreak" / "raw_small.csv"
    # --methods tiebreak는 H5, CSA_f, CSA_t를 네 기준으로 실행한다
    run.main(["--size", "small", "--methods", "tiebreak", "--reps", "1", "--scale", "0.02", "--every", "1920",
              "--workers", "1", "--out", str(out)])
    with out.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2 * 12 and {row["method"] for row in rows} == set(run.TIE_METHODS)


# ---- 집계 ----

def test_method_names_are_split_into_method_and_policy():
    assert analyze_tiebreak.split("h5") == ("h5", "first")
    assert analyze_tiebreak.split("csa_f_last") == ("csa_f", "last")
    assert analyze_tiebreak.split("csa_t_random") == ("csa_t", "random")
    assert analyze_tiebreak.split("sa_geo") == ("sa_geo", "first")
    assert analyze_tiebreak.split("sa_exp_random") == ("sa_exp", "random")
    assert analyze_tiebreak.split("csa_f_pct") is None  # 집계의 대상이 아닌 방법


def write_runs(tmp_path):
    raw, milp = tmp_path / "raw.csv", tmp_path / "milp.csv"
    rows = [
        # 인스턴스 A의 최적값은 10, B의 최적값은 0이다
        ("A", "h5", 0, 10), ("A", "h5_last", 0, 12), ("A", "csa_t", 0, 10), ("A", "csa_t", 1, 11),
        ("B", "h5", 0, 0), ("B", "h5_last", 0, 0), ("B", "csa_t", 0, 0), ("B", "csa_t", 1, 0),
        ("A", "csa_f_pct", 0, 99),
    ]
    with raw.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["instance", "method", "rep", "objective", "elapsed", "iterations"])
        writer.writerows((*row, 0.5, 7) for row in rows)
    with milp.open("w", newline="") as handle:
        csv.writer(handle).writerows([["instance", "objective"], ["A", 10], ["B", 0]])
    return raw, milp


def test_the_summary_reports_quality_by_policy_and_method(tmp_path):
    data = analyze_tiebreak.load(*write_runs(tmp_path))
    summary = analyze_tiebreak.summarize(data)
    assert set(summary) == {("first", "h5"), ("last", "h5"), ("first", "csa_t")}
    first, last, csa = summary[("first", "h5")], summary[("last", "h5")], summary[("first", "csa_t")]
    assert (first["hit"], first["mean"], first["rpd"], first["missed"]) == (100.0, 5.0, 0.0, 0)
    assert (last["hit"], last["mean"], last["rpd"], last["missed"]) == (50.0, 6.0, pytest.approx(20.0), 1)
    # CSA_t는 실행 4회 중 3회가 최적값에 도달했고, 인스턴스 A의 평균은 10.5이다
    assert (csa["hit"], csa["mean"], csa["rpd"], csa["missed"]) == (75.0, 5.25, pytest.approx(5.0), 1)
    assert csa["unstable"] == 1 and first["unstable"] == 0  # 반복 사이에 값이 달라진 인스턴스의 수


def test_policies_are_compared_with_the_first_policy_instance_by_instance(tmp_path):
    data = analyze_tiebreak.load(*write_runs(tmp_path))
    assert analyze_tiebreak.against_first(data, "h5", "last") == (0, 1, 1)  # (더 좋음, 같음, 더 나쁨)


def test_two_methods_are_compared_instance_by_instance(tmp_path):
    data = analyze_tiebreak.load(*write_runs(tmp_path))
    # 인스턴스 A에서는 CSA_t의 평균(10.5)이 H5(10)보다 크고, B에서는 같다: (둘째가 더 좋음, 같음, 둘째가 더 나쁨)
    assert analyze_tiebreak.compare(data, ("first", "h5"), ("first", "csa_t")) == (0, 1, 1)
    assert analyze_tiebreak.compare(data, ("first", "csa_t"), ("first", "h5")) == (1, 1, 0)


def test_the_sign_test_gives_the_exact_two_sided_p_value():
    assert analyze_tiebreak.sign_test(5, 5) == 1.0
    assert analyze_tiebreak.sign_test(0, 0) == 1.0  # 차이가 난 인스턴스가 없으면 판단할 수 없다
    assert analyze_tiebreak.sign_test(10, 0) == pytest.approx(2 / 1024)
    assert analyze_tiebreak.sign_test(2, 8) == pytest.approx(2 * (45 + 10 + 1) / 1024)


def test_the_reference_is_the_best_run_when_no_milp_file_is_given(tmp_path):
    raw, _ = write_runs(tmp_path)
    data = analyze_tiebreak.load(raw, None)
    assert {name: entry["opt"] for name, entry in data.items()} == {"A": 10, "B": 0}


def test_runs_are_loaded_from_several_files(tmp_path):
    raw, _ = write_runs(tmp_path)
    extra = tmp_path / "extra.csv"
    with extra.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["instance", "method", "rep", "objective", "elapsed", "iterations"])
        writer.writerow(["A", "sa_geo_random", 0, 9, 0.5, 100])
    data = analyze_tiebreak.load([raw, extra], None)
    assert data["A"]["runs"][("random", "sa_geo")] == [9] and data["A"]["runs"][("first", "h5")] == [10]
    assert data["A"]["opt"] == 9  # MILP 결과가 없으면 기준값은 모든 파일의 모든 실행 가운데 최선값이다


def test_h5_decisions_follow_the_construction_of_h5():
    for path in list_instances("small")[::320] + list_instances("medium")[::960]:
        inst = load_instance(path)
        sched = Schedule.empty(inst)
        for j, picks in analyze_tiebreak.h5_decisions(inst):
            insert(inst, sched, *picks["first"], j)
        assert sched.seqs == construct(inst).seqs, inst.name
    assert tiebreak.mode == "first"


def test_decisions_that_depend_on_the_policy_are_counted():
    # 같은 기계 2대와 같은 작업 2개: 첫 작업은 어느 기계에 넣어도 같고, 둘째 작업은 빈 기계가 더 좋다
    assert analyze_tiebreak.decision_ties(two_machines([[1, 1], [1, 1]], [1, 1])) == (2, 1, 0)
    # 기계 1이 더 빠르고 지연은 생기지 않는다: 두 결정 모두 기준 last, csum에서는 기계 1을 고른다
    assert analyze_tiebreak.decision_ties(two_machines([[3, 3], [1, 1]], [9, 9])) == (2, 2, 2)
