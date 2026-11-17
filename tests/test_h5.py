from src.h5 import h5
from src.instance import Instance, list_instances, load_instance
from src.schedule import validate
from tests.helpers import brute_force_optimum, tiny_instance


def no_setup(n, m):
    return [[[0] * n for _ in range(n)] for _ in range(m)]


def test_h5_on_the_hand_example():
    # 적격 기계가 1대인 작업 2, 3을 먼저 배정하고, 이어서 작업 0, 1을 납기 순으로 배정한다
    sched = h5(tiny_instance())
    assert sched.seqs == [[0, 2], [1, 3]]
    assert sched.total == 2


def test_repair_moves_the_most_tardy_job_to_an_empty_machine():
    # 기계 1이 느려서 구성 단계에서는 세 작업이 모두 기계 0에 배정된다([2, 1, 0], 지연 0, 1, 2)
    inst = Instance("repair", 3, 2, [[1, 1, 1], [5, 5, 5]], no_setup(3, 2), [1, 1, 1], [[True] * 3, [True] * 3])
    sched = h5(inst)
    assert sched.seqs == [[1, 2], [0]]
    assert sched.total == 5
    assert validate(inst, sched) == []


def test_repair_does_nothing_when_no_job_is_tardy():
    inst = Instance("on-time", 2, 2, [[1, 1], [5, 5]], no_setup(2, 2), [100, 100], [[True] * 2, [True] * 2])
    sched = h5(inst)
    assert sched.seqs == [[1, 0], []]
    assert sched.total == 0


def test_h5_returns_valid_schedules_on_benchmark_instances():
    for path in list_instances("small")[::40] + list_instances("medium")[::40]:
        inst = load_instance(path)
        assert validate(inst, h5(inst)) == [], inst.name


def test_h5_is_never_better_than_the_optimum():
    for path in list_instances("small")[:240:24]:  # n = 6, m = 2
        inst = load_instance(path)
        assert h5(inst).total >= brute_force_optimum(inst), inst.name
