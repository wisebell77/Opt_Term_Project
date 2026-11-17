"""건설적 휴리스틱 H5: 구성(논문의 Algorithm 4), 보정(Repair), 개선(IP)."""
from __future__ import annotations

from .insertion import best_position, best_position_total, insert
from .schedule import Schedule, job_tardiness


def construct(inst):
    """적격 기계가 적은 작업부터, 같은 그룹 안에서는 납기가 이른 작업부터 삽입한다."""
    sched = Schedule.empty(inst)
    for j in sorted(range(inst.n), key=lambda j: (len(inst.elig[j]), inst.d[j], j)):
        if len(inst.elig[j]) == 1:
            i = inst.elig[j][0]
            pos = best_position(inst, i, sched.seqs[i], j)[2]
        else:
            i, pos = best_position_total(inst, sched, j)
        insert(inst, sched, i, pos, j)
    return sched


def most_tardy(inst, sched, machines, allowed=None):
    """machines에 놓인 작업 중 지연이 가장 큰 작업의 (지연, 기계, 위치). 대상 작업이 없으면 None이다."""
    best = None
    for i in machines:
        seq = sched.seqs[i]
        for pos, tard in enumerate(job_tardiness(inst, i, seq)):
            if (allowed is None or allowed[seq[pos]]) and (best is None or tard > best[0]):
                best = (tard, i, pos)
    return best


def repair(inst, sched):
    """빈 기계가 있으면, 그 기계에서 처리할 수 있는 작업 중 지연이 가장 큰 작업을 옮겨 온다."""
    for empty in range(inst.m):
        if sched.seqs[empty]:
            continue
        found = most_tardy(inst, sched, range(inst.m), inst.ok[empty])
        if found is None:
            continue
        tard, i, pos = found
        # 지연이 0이거나, 원래 기계에 작업이 하나뿐이면 옮기지 않는다
        if tard == 0 or len(sched.seqs[i]) < 2:
            continue
        seq = sched.seqs[i]
        j = seq[pos]
        sched.set_machine(inst, i, seq[:pos] + seq[pos + 1 :])
        sched.set_machine(inst, empty, [j])


def improve(inst, sched):
    """지연이 있고 작업이 2개 이상인 기계마다, 지연이 가장 큰 작업을 꺼내어 최선 위치에 다시 넣는다."""
    if sched.total == 0:
        return
    for i in range(inst.m):
        seq = sched.seqs[i]
        if sched.tard[i] == 0 or len(seq) < 2:
            continue
        pos = most_tardy(inst, sched, [i])[2]
        j = seq[pos]
        sched.set_machine(inst, i, seq[:pos] + seq[pos + 1 :])
        insert(inst, sched, *best_position_total(inst, sched, j), j)


def h5(inst):
    sched = construct(inst)
    repair(inst, sched)
    improve(inst, sched)
    return sched
