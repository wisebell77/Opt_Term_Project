import random

from src.insertion import best_position, best_position_total
from src.instance import Instance, list_instances, load_instance
from src.schedule import Schedule, machine_cost
from tests.helpers import tiny_instance


def random_partial(inst, rng):
    """작업의 절반가량을 무작위 적격 기계의 무작위 위치에 넣은 부분 해와 남은 작업."""
    jobs = list(range(inst.n))
    rng.shuffle(jobs)
    cut = inst.n // 2
    seqs = [[] for _ in range(inst.m)]
    for j in jobs[:cut]:
        seq = seqs[rng.choice(inst.elig[j])]
        seq.insert(rng.randint(0, len(seq)), j)
    return Schedule.from_seqs(inst, seqs), jobs[cut:]


def sample_instances():
    small, medium = list_instances("small"), list_instances("medium")
    return [load_instance(p) for p in small[::640] + medium[::480]]


def test_best_position_matches_trying_every_position():
    rng = random.Random(1)
    for inst in sample_instances():
        sched, rest = random_partial(inst, rng)
        for j in rest:
            for i in inst.elig[j]:
                seq = sched.seqs[i]
                expected = min(
                    machine_cost(inst, i, seq[:pos] + [j] + seq[pos:]) + (pos,) for pos in range(len(seq) + 1)
                )
                assert best_position(inst, i, seq, j) == expected, (inst.name, i, j)


def test_best_position_total_matches_trying_every_machine_and_position():
    rng = random.Random(2)
    for inst in sample_instances():
        sched, rest = random_partial(inst, rng)
        for j in rest:
            options = []
            for i in inst.elig[j]:
                seq = sched.seqs[i]
                for pos in range(len(seq) + 1):
                    tard, csum = machine_cost(inst, i, seq[:pos] + [j] + seq[pos:])
                    options.append((tard - sched.tard[i], csum - sched.csum[i], i, pos))
            assert best_position_total(inst, sched, j) == min(options)[2:], (inst.name, j)


def test_ties_in_tardiness_are_broken_by_completion_time_sum():
    inst = tiny_instance()
    # 기계 1에 작업 1을 넣는 두 위치 모두 지연이 0이다: [1, 3]은 완료시간 합 8, [3, 1]은 11
    assert best_position(inst, 1, [3], 1) == (0, 8, 0)


def test_remaining_ties_go_to_the_earliest_machine_and_position():
    zero = [[0, 0], [0, 0]]
    inst = Instance("tie", 2, 2, [[1, 1], [1, 1]], [zero, zero], [1, 1], [[True, True], [True, True]])
    sched = Schedule.from_seqs(inst, [[0], []])
    # 기계 0의 어느 위치에 넣어도 (지연 1, 완료시간 합 3)이고, 기계 1에 넣으면 지연이 없다
    assert best_position(inst, 0, [0], 1) == (1, 3, 0)
    assert best_position_total(inst, sched, 1) == (1, 0)
    assert best_position_total(inst, Schedule.empty(inst), 0) == (0, 0)
