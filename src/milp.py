"""MILP 모형 (Perez-Gonzalez et al., 2019의 식 (1)-(11))을 Gurobi로 푼다.

논문은 비적격 기계의 가공시간을 매우 큰 값으로 두지만, 여기서는 비적격 기계에 해당하는 변수를
만들지 않는다. 두 방식의 최적값은 같다. 더미 작업 0은 번호 -1로 표현한다.
"""
from __future__ import annotations

from .schedule import Schedule

DUMMY = -1


def solve_milp(inst, time_limit=100.0):
    """최적해를 구하여 {"objective", "optimal", "bound", "runtime", "schedule"}로 돌려준다."""
    import gurobipy as gp
    from gurobipy import GRB

    machines, jobs = range(inst.m), range(inst.n)
    model = gp.Model(inst.name)
    model.Params.OutputFlag = 0
    model.Params.TimeLimit = time_limit

    # x[i, j, k] = 1: 기계 i에서 작업 j 바로 다음에 작업 k를 처리한다
    arcs = [(i, j, k) for i in machines for k in inst.jobs_of[i] for j in [DUMMY] + inst.jobs_of[i] if j != k]
    x = model.addVars(arcs, vtype=GRB.BINARY)
    # 기계 i의 완료시간 상한: 모든 적격 작업을 가장 긴 준비시간과 함께 처리하는 경우
    horizon = [
        sum(inst.p[i][j] + max(inst.s[i][h][j] for h in inst.jobs_of[i]) for j in inst.jobs_of[i]) for i in machines
    ]
    c = model.addVars([(i, j) for i in machines for j in inst.jobs_of[i]], lb=0.0, ub={(i, j): horizon[i] for i in machines for j in inst.jobs_of[i]})
    t = model.addVars(jobs, lb=0.0)
    model.setObjective(t.sum(), GRB.MINIMIZE)  # (1)

    for i in machines:
        eligible = inst.jobs_of[i]
        big = horizon[i] + max(inst.s[i][j][k] + inst.p[i][k] for j in eligible for k in eligible)
        model.addConstr(x.sum(i, DUMMY, "*") <= 1)  # (5) 기계마다 첫 작업은 하나 이하
        for j in eligible:
            model.addConstr(t[j] >= c[i, j] - inst.d[j])  # (2)
            # (7) 더미 작업 다음에 오는 첫 작업에는 준비시간이 없다
            model.addConstr(c[i, j] + big * (1 - x[i, DUMMY, j]) >= inst.p[i][j])
            for k in eligible:
                if j != k:
                    model.addConstr(x.sum(i, "*", j) >= x[i, j, k])  # (6) 선행 작업이 있어야 후속 작업을 둘 수 있다
                    model.addConstr(c[i, k] + big * (1 - x[i, j, k]) >= c[i, j] + inst.s[i][j][k] + inst.p[i][k])  # (7)
    for k in jobs:
        model.addConstr(gp.quicksum(x.sum(i, "*", k) for i in inst.elig[k]) == 1)  # (3) 선행 작업은 정확히 하나
        model.addConstr(gp.quicksum(x.sum(i, k, "*") for i in inst.elig[k]) <= 1)  # (4) 후속 작업은 하나 이하

    model.optimize()

    seqs = []
    for i in machines:
        seq, prev = [], DUMMY
        while True:
            following = [k for k in inst.jobs_of[i] if k != prev and x[i, prev, k].X > 0.5]
            if not following:
                break
            prev = following[0]
            seq.append(prev)
        seqs.append(seq)
    return {
        "objective": int(round(model.ObjVal)),
        "optimal": model.Status == GRB.OPTIMAL,
        "bound": model.ObjBound,
        "runtime": model.Runtime,
        "schedule": Schedule.from_seqs(inst, seqs),
    }
