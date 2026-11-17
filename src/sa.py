"""개선 방법 SA_t: H5의 해에서 출발하는 시뮬레이티드 어닐링.

냉각 방식은 "geo"(기하, 대표 설정), "log"(로그), "exp"(지수) 중 하나를 고른다.
"""
from __future__ import annotations

import math

from .budget import Result
from .h5 import h5
from .schedule import machine_cost

K_STEPS = 100  # 냉각 단계 수 K
ALPHA_MAX = 0.9  # 지수 냉각 계수의 상한
ACCEPT_START = 0.80  # 초기 온도에서의 목표 평균 수락 확률
ACCEPT_END = 0.01  # 목표 종료 온도에서의 목표 평균 수락 확률
SAMPLE_SIZE = 100  # 온도 설정에 사용하는 양의 증가량 표본 수 q
SAMPLE_TRIES = 2000  # 표본을 모으기 위해 시도하는 이웃의 최대 개수


def temperatures(t0, tf, steps, cooling, n, alpha_max=ALPHA_MAX):
    """k = 0, ..., steps 단계의 온도 목록. n은 작업 수이며 지수 냉각에만 사용한다."""
    ks = range(steps + 1)
    if cooling == "geo":
        alpha = (tf / t0) ** (1 / steps)
        return [t0 * alpha**k for k in ks]
    if cooling == "log":
        b = (t0 / tf - 1) / math.log(1 + steps)
        return [t0 / (1 + b * math.log(1 + k)) for k in ks]
    if cooling == "exp":
        alpha = min(math.log(t0 / tf) / steps ** (1 / n), alpha_max)
        return [t0 * math.exp(-alpha * k ** (1 / n)) for k in ks]
    raise ValueError(f"알 수 없는 냉각 방식: {cooling}")


def fit_temperature(deltas, target):
    """증가량 표본의 평균 수락 확률 mean(exp(-Δ/T))이 target이 되는 온도 T를 이분법으로 구한다."""

    def acceptance(temp):
        return sum(math.exp(-x / temp) for x in deltas) / len(deltas)

    low, high = float(min(deltas)), float(max(deltas))
    while acceptance(low) > target:
        low /= 2
    while acceptance(high) < target:
        high *= 2
    for _ in range(100):
        mid = (low + high) / 2
        if acceptance(mid) < target:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def propose(inst, sched, where, rng):
    """무작위 이웃 하나를 만들어 (종류, [(기계, 새 순서, 비용)], 총 지연 변화량, [(작업, 새 기계)])로 돌려준다.

    where[j]는 작업 j가 놓인 기계이다. 적격성을 만족하는 이웃을 찾지 못하면 None을 돌려준다.
    """
    for _ in range(50):
        kind = rng.randrange(3)
        j = rng.randrange(inst.n)
        i = where[j]
        seq_i = sched.seqs[i]
        a = seq_i.index(j)
        if kind == 0:  # 내부 삽입: 같은 기계의 다른 위치로 옮긴다
            if len(seq_i) < 2:
                continue
            b = rng.randrange(len(seq_i) - 1)
            b += b >= a
            rest = seq_i[:a] + seq_i[a + 1 :]
            new_i = rest[:b] + [j] + rest[b:]
            cost_i = machine_cost(inst, i, new_i)
            return "internal_insert", [(i, new_i, cost_i)], cost_i[0] - sched.tard[i], []
        if kind == 1:  # 외부 삽입: 다른 적격 기계의 임의 위치로 옮긴다
            targets = [w for w in inst.elig[j] if w != i]
            if not targets:
                continue
            w = rng.choice(targets)
            seq_w = sched.seqs[w]
            pos = rng.randrange(len(seq_w) + 1)
            new_i = seq_i[:a] + seq_i[a + 1 :]
            new_w = seq_w[:pos] + [j] + seq_w[pos:]
            name, relocations = "external_insert", [(j, w)]
        else:  # 외부 교환: 다른 기계의 작업과 맞바꾼다
            other = rng.randrange(inst.n)
            w = where[other]
            if w == i or not inst.ok[w][j] or not inst.ok[i][other]:
                continue
            seq_w = sched.seqs[w]
            new_i, new_w = seq_i[:], seq_w[:]
            new_i[a], new_w[seq_w.index(other)] = other, j
            name, relocations = "external_swap", [(j, w), (other, i)]
        cost_i, cost_w = machine_cost(inst, i, new_i), machine_cost(inst, w, new_w)
        delta = cost_i[0] + cost_w[0] - sched.tard[i] - sched.tard[w]
        return name, [(i, new_i, cost_i), (w, new_w, cost_w)], delta, relocations
    return None


def sa_t(inst, rng, budget, cooling="geo"):
    budget.start()
    current = h5(inst)
    best = current.copy()
    if best.total == 0:
        return Result(best, 0, budget.elapsed(), 0, {"cooling": cooling})
    where = [0] * inst.n
    for i, seq in enumerate(current.seqs):
        for j in seq:
            where[j] = i

    # 온도 설정: H5 해의 이웃에서 양의 증가량 표본을 모아 목표 수락 확률에 맞춘다
    deltas = []
    for _ in range(SAMPLE_TRIES):
        move = propose(inst, current, where, rng)
        if move is not None and move[2] > 0:
            deltas.append(move[2])
            if len(deltas) == SAMPLE_SIZE:
                break
    deltas = deltas or [1]
    t0, tf = fit_temperature(deltas, ACCEPT_START), fit_temperature(deltas, ACCEPT_END)
    temps = temperatures(t0, tf, K_STEPS, cooling, inst.n)

    accepted = 0
    temp = temps[0]
    trace = [(0, best.total)]  # (평가 횟수, 그때까지의 최선값)
    while best.total > 0 and not budget.done():
        temp = temps[min(K_STEPS, int((K_STEPS + 1) * budget.progress()))]
        move = propose(inst, current, where, rng)
        budget.tick()
        if move is None:
            continue
        _, changes, delta, relocations = move
        if delta <= 0 or rng.random() < math.exp(-delta / temp):
            for i, seq, cost in changes:
                current.set_machine(inst, i, seq, cost)
            for j, i in relocations:
                where[j] = i
            accepted += 1
            if current.total < best.total:
                best = current.copy()
                trace.append((budget.iters, best.total))
    info = {"cooling": cooling, "t0": t0, "tf": tf, "t_end": temp, "accepted": accepted, "trace": trace}
    return Result(best, best.total, budget.elapsed(), budget.iters, info)
