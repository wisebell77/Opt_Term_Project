"""테스트에서만 사용하는 보조 함수."""
from itertools import permutations, product

from src.instance import DATA_DIR, Instance, load_instance
from src.schedule import machine_cost


def tiny_instance():
    """손으로 계산할 수 있는 2기계 4작업 예제. 작업 2는 기계 0, 작업 3은 기계 1에서만 처리할 수 있다."""
    p = [[3, 5, 2, 4], [6, 2, 7, 3]]
    s = [
        [[0, 2, 3, 1], [4, 0, 1, 2], [2, 3, 0, 5], [1, 1, 2, 0]],
        [[0, 1, 2, 3], [3, 0, 4, 1], [1, 2, 0, 2], [2, 3, 1, 0]],
    ]
    d = [4, 9, 6, 8]
    ok = [[True, True, True, False], [True, True, False, True]]
    return Instance("tiny", 4, 2, p, s, d, ok)


# 최적 총 지연이 0보다 큰 인스턴스. 벤치마크의 다수는 최적값이 0이어서 탐색 과정을 시험하기에 부족하다.
HARD = [
    "small/I_6_2_49_50_T04_R02_1",
    "small/I_6_3_124_80_T04_R02_1",
    "small/I_6_4_49_50_T02_R02_1",
    "medium/I_15_2_49_100_T02_R02_1",
    "medium/I_15_2_124_100_T04_R02_1",
    "medium/I_15_6_49_100_T04_R02_1",
    "medium/I_20_4_124_100_T04_R02_1",
]


def hard_instance(index):
    return load_instance(DATA_DIR / (HARD[index] + ".txt"))


def hard_instances():
    return [hard_instance(index) for index in range(len(HARD))]


def brute_force_optimum(inst):
    """모든 배정과 모든 순서를 시도하여 최적 총 지연을 구한다. n이 6 이하일 때만 사용한다."""
    best = None
    for assign in product(*[inst.elig[j] for j in range(inst.n)]):
        total = 0
        for i in range(inst.m):
            jobs = [j for j in range(inst.n) if assign[j] == i]
            total += min(machine_cost(inst, i, list(seq))[0] for seq in permutations(jobs))
            if best is not None and total >= best:
                break
        else:
            best = total
    return best
