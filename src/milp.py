"""MILP 모형 (Perez-Gonzalez et al., 2019의 식 (1)-(11))을 Gurobi로 푼다.

기본(tight=False)은 논문의 모형을 그대로 따른다.
- 모든 기계 i와 작업 쌍 (j, k)에 이진 변수 X[i,j,k]를 둔다(j는 더미 작업 0을 포함, 더미는 번호 -1).
- 적격성은 모형에 넣지 않고 자료에서 처리한다. 비적격 기계의 가공시간을 매우 큰 값으로 둔다(논문 4절 끝).
- 식 (2)는 모든 기계에 대해, 식 (6)은 h != j인 모든 h에 대해 건다. 식 (7)의 V는 하나의 큰 수이다.
- 완료시간 C[i,j]에는 식 (11)의 하한 0 외에 상한을 두지 않는다.
논문이 "very large"라고만 적은 값(비적격 가공시간)과 "big number"(V)는 자료에서 계산한다: 적격 기계만 쓰는
어떤 해의 총 지연보다 큰 값을 가공시간으로, 그 값에 모든 적격 완료시간의 상한을 더한 값을 V로 쓴다.

tight=True는 이전 구현이다. 비적격 기계의 변수를 만들지 않고, 완료시간 상한과 기계별 big-M을 쓴다.
두 방식의 최적값은 같지만 tight 쪽이 풀기 쉽다.
"""
from __future__ import annotations

from .schedule import Schedule

DUMMY = -1


def solve_milp(inst, time_limit=100.0, tight=False):
    """최적해를 구하여 {"objective", "optimal", "bound", "runtime", "schedule", "consistent"}로 돌려준다.

    time_limit이 None이면 시간 제한 없이 푼다. consistent는 모형이 낸 목적함수값이 돌려준 해를
    다시 계산한 값과 같은지(big-M으로 인한 수치 오차가 없는지)를 나타낸다.
    """
    import gurobipy as gp
    from gurobipy import GRB

    machines, jobs = range(inst.m), range(inst.n)
    model = gp.Model(inst.name)
    model.Params.OutputFlag = 0
    if time_limit is not None:
        model.Params.TimeLimit = time_limit
    model.Params.IntFeasTol = 1e-9  # big-M 제약에서 0이 아닌 이진 변수의 허용 오차가 해를 바꾸지 않도록 한다

    if tight:
        candidates = [inst.jobs_of[i] for i in machines]
        x, c, t = _build_tight(inst, model, gp, GRB)
    else:
        candidates = [list(jobs) for _ in machines]
        x, c, t = _build_faithful(inst, model, gp, GRB)

    model.optimize()

    seqs = []
    for i in machines:
        seq, prev = [], DUMMY
        while True:
            following = [k for k in candidates[i] if k != prev and x[i, prev, k].X > 0.5]
            if not following:
                break
            prev = following[0]
            seq.append(prev)
        seqs.append(seq)
    schedule = Schedule.from_seqs(inst, seqs)
    objective = int(round(model.ObjVal))
    return {
        "objective": objective,
        "optimal": model.Status == GRB.OPTIMAL,
        "bound": model.ObjBound,
        "runtime": model.Runtime,
        "schedule": schedule,
        "consistent": schedule.total == objective and all(inst.ok[i][j] for i, seq in enumerate(seqs) for j in seq),
    }


def _build_faithful(inst, model, gp, GRB):
    machines, jobs = range(inst.m), range(inst.n)
    dummy_and_jobs = [DUMMY] + list(jobs)

    # 적격 기계에서 어떤 해가 가질 수 있는 완료시간의 상한과, 그보다 큰 "매우 큰" 가공시간
    horizon = sum(
        max(inst.p[i][j] for i in inst.elig[j]) + max(inst.s[i][h][j] for i in inst.elig[j] for h in jobs if h != j)
        if inst.n > 1 else max(inst.p[i][j] for i in inst.elig[j])
        for j in jobs
    )
    huge = (inst.n + 2) * horizon
    p = [[inst.p[i][j] if inst.ok[i][j] else huge for j in jobs] for i in machines]
    big = huge + horizon + max(max(row) for row in p)  # V

    # X[i, j, k] = 1: 기계 i에서 작업 j 바로 다음에 작업 k를 처리한다 (j는 더미 포함)
    x = model.addVars([(i, j, k) for i in machines for j in dummy_and_jobs for k in jobs if j != k], vtype=GRB.BINARY)
    c = model.addVars(machines, jobs, lb=0.0)  # (11)
    t = model.addVars(jobs, lb=0.0)  # (10)
    model.setObjective(t.sum(), GRB.MINIMIZE)  # (1)

    for j in jobs:
        for i in machines:
            model.addConstr(t[j] >= c[i, j] - inst.d[j])  # (2)
    for k in jobs:
        model.addConstr(gp.quicksum(x[i, j, k] for i in machines for j in dummy_and_jobs if j != k) == 1)  # (3)
        model.addConstr(gp.quicksum(x[i, k, h] for i in machines for h in jobs if h != k) <= 1)  # (4)
    for i in machines:
        model.addConstr(gp.quicksum(x[i, DUMMY, k] for k in jobs) <= 1)  # (5)
        for j in jobs:
            for k in jobs:
                if j != k:
                    # (6) j 다음에 k를 두려면 j에 선행 작업(더미 포함)이 있어야 한다
                    model.addConstr(gp.quicksum(x[i, h, j] for h in dummy_and_jobs if h != j) >= x[i, j, k])
        for k in jobs:
            # (7) j = 0(더미)이면 C[i,0] = 0(식 (8))이고 준비시간은 0이다
            model.addConstr(c[i, k] + big * (1 - x[i, DUMMY, k]) >= p[i][k])
            for j in jobs:
                if j != k:
                    model.addConstr(c[i, k] + big * (1 - x[i, j, k]) >= c[i, j] + inst.s[i][j][k] + p[i][k])
    return x, c, t


def _build_tight(inst, model, gp, GRB):
    machines, jobs = range(inst.m), range(inst.n)

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
        model.addConstr(x.sum(i, DUMMY, "*") <= 1)  # (5)
        for j in eligible:
            model.addConstr(t[j] >= c[i, j] - inst.d[j])  # (2)
            model.addConstr(c[i, j] + big * (1 - x[i, DUMMY, j]) >= inst.p[i][j])  # (7), 더미 다음의 첫 작업
            for k in eligible:
                if j != k:
                    model.addConstr(x.sum(i, "*", j) >= x[i, j, k])  # (6)
                    model.addConstr(c[i, k] + big * (1 - x[i, j, k]) >= c[i, j] + inst.s[i][j][k] + inst.p[i][k])  # (7)
    for k in jobs:
        model.addConstr(gp.quicksum(x.sum(i, "*", k) for i in inst.elig[k]) == 1)  # (3)
        model.addConstr(gp.quicksum(x.sum(i, k, "*") for i in inst.elig[k]) <= 1)  # (4)
    return x, c, t
