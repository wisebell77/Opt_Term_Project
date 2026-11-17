"""해 표현과 평가.

해는 기계별 작업 순서 리스트이다. 기계별 지연 합과 완료시간 합을 저장해 두고,
순서가 바뀐 기계만 다시 계산한다(증분 평가).
"""
from __future__ import annotations


def machine_cost(inst, i, seq):
    """기계 i에서 seq 순서로 처리할 때의 (지연 합, 완료시간 합). 첫 작업에는 준비시간이 없다."""
    p, s, d = inst.p[i], inst.s[i], inst.d
    t = tard = csum = 0
    prev = -1
    for j in seq:
        t += p[j] if prev < 0 else s[prev][j] + p[j]
        if t > d[j]:
            tard += t - d[j]
        csum += t
        prev = j
    return tard, csum


def job_tardiness(inst, i, seq):
    """기계 i에서 seq 순서로 처리할 때 위치별 작업의 순수지연시간."""
    p, s, d = inst.p[i], inst.s[i], inst.d
    t, prev, out = 0, -1, []
    for j in seq:
        t += p[j] if prev < 0 else s[prev][j] + p[j]
        out.append(max(t - d[j], 0))
        prev = j
    return out


class Schedule:
    """기계별 작업 순서와 그 비용. total은 목적함수값(총 순수지연시간)이다."""

    __slots__ = ("seqs", "tard", "csum", "total")

    def __init__(self, seqs, tard, csum):
        self.seqs = seqs
        self.tard = tard
        self.csum = csum
        self.total = sum(tard)

    @classmethod
    def from_seqs(cls, inst, seqs):
        costs = [machine_cost(inst, i, seq) for i, seq in enumerate(seqs)]
        return cls([list(seq) for seq in seqs], [c[0] for c in costs], [c[1] for c in costs])

    @classmethod
    def empty(cls, inst):
        return cls([[] for _ in range(inst.m)], [0] * inst.m, [0] * inst.m)

    def copy(self):
        return Schedule([seq[:] for seq in self.seqs], self.tard[:], self.csum[:])

    def set_machine(self, inst, i, seq, cost=None):
        """기계 i의 순서를 seq로 바꾸고 비용을 갱신한다. 이미 계산한 비용이 있으면 cost로 넘긴다."""
        tard, csum = cost if cost is not None else machine_cost(inst, i, seq)
        self.total += tard - self.tard[i]
        self.seqs[i], self.tard[i], self.csum[i] = seq, tard, csum


def validate(inst, sched):
    """해의 문제점을 문자열 목록으로 돌려준다. 유효한 해이면 빈 목록이다."""
    problems = []
    count = [0] * inst.n
    for i, seq in enumerate(sched.seqs):
        for j in seq:
            count[j] += 1
            if not inst.ok[i][j]:
                problems.append(f"작업 {j}이(가) 비적격 기계 {i}에 배정됨")
        if machine_cost(inst, i, seq) != (sched.tard[i], sched.csum[i]):
            problems.append(f"기계 {i}의 저장된 비용이 다시 계산한 값과 다름")
    problems += [f"작업 {j}이(가) {c}번 배정됨" for j, c in enumerate(count) if c != 1]
    if sched.total != sum(sched.tard):
        problems.append("저장된 목적함수값이 기계별 지연 합의 합계와 다름")
    return problems
