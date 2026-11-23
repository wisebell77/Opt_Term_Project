"""SA_t 진단: 소규모에서 SA_t(기하)가 거의 항상 최적값에 도달하는 이유를 살핀다.

사용 예 (codes 폴더에서 실행):
    python -m experiments.diagnose_sa --workers 4

대상은 최적값이 양수인 소규모 인스턴스이며, 출발해인 H5에는 팀의 동점 처리 기준을 적용한다.
다음 조건으로 실행하여 results/diagnostics/sa_budget_small.csv에 기록한다.

    full:    본 실험과 같은 시간 제한. 최적값을 처음 찾은 평가 횟수(found_at)를 본다
    scale:   시간 제한을 0.3, 0.1, 0.03, 0.01배로 줄인 실행
    descent: 같은 이웃과 같은 시간 제한에서, 나빠지는 이동을 받아들이지 않는 실행(냉각 방식 "none")

이어서 H5의 해에서 SA_t의 이동 몇 번으로 최적값에 닿는지(0, 1, 2, 3번 이상)를 센다.
"""
from __future__ import annotations

import argparse
import csv
import random
import statistics as st
from collections import Counter
from multiprocessing import Pool

from experiments.run import make_seed
from src import tiebreak
from src.budget import Budget, time_limit_seconds
from src.h5 import h5
from src.instance import DATA_DIR, RESULTS_DIR, load_instance
from src.sa import sa_t
from src.schedule import machine_cost

SETTINGS = [("full", 1.0), ("scale", 0.3), ("scale", 0.1), ("scale", 0.03), ("scale", 0.01), ("descent", 1.0)]
FIELDS = ["instance", "n", "m", "mode", "scale", "rep", "opt", "start", "objective", "evals", "found_at", "accepted"]


def run(task):
    name, opt, mode, scale, rep = task
    inst = load_instance(DATA_DIR / "small" / f"{name}.txt")
    rng = random.Random(make_seed(name, f"diagnose_{mode}_{scale}", rep))
    with tiebreak.policy(tiebreak.BASELINE, rng):
        result = sa_t(inst, rng, Budget(time_limit=time_limit_seconds(inst, scale)), "none" if mode == "descent" else "geo")
    trace = result.info["trace"]
    found_at = trace[-1][0] if result.objective == opt else ""
    return [name, inst.n, inst.m, mode, scale, rep, opt, trace[0][1], result.objective, result.iterations, found_at,
            result.info["accepted"]]


def neighbors(inst, seqs):
    """SA_t의 세 이동(내부 삽입, 외부 삽입, 외부 교환)으로 만들 수 있는 모든 이웃을 [(기계, 새 순서), ...]로 내놓는다."""
    for i, seq in enumerate(seqs):
        for a, j in enumerate(seq):
            rest = seq[:a] + seq[a + 1 :]
            for b in range(len(seq)):
                if b != a:
                    yield [(i, rest[:b] + [j] + rest[b:])]
            for w in inst.elig[j]:
                if w != i:
                    for pos in range(len(seqs[w]) + 1):
                        yield [(i, rest), (w, seqs[w][:pos] + [j] + seqs[w][pos:])]
    for i in range(inst.m):
        for w in range(i + 1, inst.m):
            for a, ja in enumerate(seqs[i]):
                for b, jb in enumerate(seqs[w]):
                    if inst.ok[w][ja] and inst.ok[i][jb]:
                        seq_i, seq_w = seqs[i][:], seqs[w][:]
                        seq_i[a], seq_w[b] = jb, ja
                        yield [(i, seq_i), (w, seq_w)]


def costs_after(inst, sched, changes):
    """이웃으로 옮긴 뒤의 기계별 지연 합."""
    tard = sched.tard[:]
    for i, seq in changes:
        tard[i] = machine_cost(inst, i, seq)[0]
    return tard


def distance(inst, sched, target):
    """sched에서 SA_t의 이동 몇 번으로 총 지연 target에 닿는지: 0, 1, 2 또는 3(3번 이상)."""
    if sched.total == target:
        return 0
    first = []
    for changes in neighbors(inst, sched.seqs):
        tard = costs_after(inst, sched, changes)
        if sum(tard) == target:
            return 1
        seqs = sched.seqs[:]
        for i, seq in changes:
            seqs[i] = seq
        first.append((seqs, tard))
    for seqs, tard in first:
        base = sum(tard)
        for changes in neighbors(inst, seqs):
            if base + sum(machine_cost(inst, i, seq)[0] - tard[i] for i, seq in changes) == target:
                return 2
    return 3


def h5_distance(task):
    name, opt = task
    inst = load_instance(DATA_DIR / "small" / f"{name}.txt")
    with tiebreak.policy(tiebreak.BASELINE, random.Random(make_seed(name, "diagnose_distance", 0))):
        sched = h5(inst)
    return distance(inst, sched, opt)


def quantile(values, share):
    values = sorted(values)
    return values[min(len(values) - 1, int(share * len(values)))]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--every", type=int, default=1, help="k번째 인스턴스마다 하나씩만 실행(시험용)")
    args = parser.parse_args()

    with (RESULTS_DIR / "milp_small.csv").open(newline="") as handle:
        optimum = {row["instance"]: int(float(row["objective"])) for row in csv.DictReader(handle)}
    names = sorted(name for name, value in optimum.items() if value > 0)[:: args.every]
    tasks = [(name, optimum[name], mode, scale, rep) for name in names for mode, scale in SETTINGS for rep in range(args.reps)]
    with Pool(args.workers) as pool:
        rows = pool.map(run, tasks, chunksize=6)
        distances = Counter(pool.map(h5_distance, [(name, optimum[name]) for name in names], chunksize=8))
    out = RESULTS_DIR / "diagnostics" / "sa_budget_small.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(FIELDS)
        writer.writerows(rows)

    print(f"최적값이 양수인 소규모 인스턴스 {len(names)}개, 반복 {args.reps}회 -> {out.relative_to(RESULTS_DIR.parent)}")
    print("\n[1] 조건별 최적 도달")
    for mode, scale in SETTINGS:
        part = [row for row in rows if (row[3], row[4]) == (mode, scale)]
        need = [row for row in part if row[7] != row[6]]  # 출발해가 최적이 아니어서 탐색이 필요한 실행
        print(f"  {mode:8s} x{scale:<5} | 도달 {100 * st.mean(row[8] == row[6] for row in part):6.2f}% "
              f"| 탐색이 필요한 실행 {len(need):5d}회 중 도달 {100 * st.mean(row[8] == row[6] for row in need):6.2f}% "
              f"| 평가 횟수의 중앙값 {int(st.median(row[9] for row in part)):,}")

    found = [row for row in rows if row[3] == "full" and row[7] != row[6] and row[10] != ""]
    share = [row[10] / row[9] for row in found]
    print(f"\n[2] 본 실험 조건에서 최적값을 처음 찾은 시점(탐색이 필요했고 최적값을 찾은 실행 {len(found)}회)")
    print(f"  평가 횟수: 중앙값 {int(st.median(row[10] for row in found)):,}, 최대 {max(row[10] for row in found):,}")
    print(f"  시간 제한 대비: 중앙값 {100 * st.median(share):.2f}%, 90% 지점 {100 * quantile(share, 0.9):.1f}%, "
          f"99% 지점 {100 * quantile(share, 0.99):.1f}%, 최대 {100 * max(share):.1f}%")

    total = sum(distances.values())
    print("\n[3] H5의 해에서 최적값까지 필요한 이동 횟수")
    for moves, label in ((0, "이미 최적"), (1, "1번"), (2, "2번"), (3, "3번 이상")):
        print(f"  {label:6s} {distances[moves]:4d}개 ({100 * distances[moves] / total:.1f}%)")


if __name__ == "__main__":
    main()
