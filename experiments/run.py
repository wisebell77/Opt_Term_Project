"""실험 실행기: 인스턴스마다 모든 방법과 모든 반복을 실행하여 results/raw_<크기>_<태그>.csv에 기록한다.

사용 예 (codes 폴더에서 실행):
    python -m experiments.run --size small
    python -m experiments.run --size medium --shard 0/3 --tag laptop_a

한 인스턴스의 모든 방법과 반복은 같은 프로세스에서 실행되므로, 여러 노트북에 나눌 때에는
--shard로 인스턴스 단위로 나눈다. 중단한 뒤 같은 명령을 다시 실행하면 끝난 부분은 건너뛴다.
"""
from __future__ import annotations

import argparse
import csv
import os
import platform
import random
import re
import zlib
from multiprocessing import Pool
from pathlib import Path

from src.budget import Budget, Result, time_limit_seconds
from src.csa import csa_f, csa_t
from src.h5 import h5
from src.instance import RESULTS_DIR, list_instances, load_instance, parse_name
from src.sa import sa_t
from src.schedule import validate


def run_h5(inst, rng, budget):
    budget.start()
    sched = h5(inst)
    return Result(sched, sched.total, budget.elapsed(), 0)


# 방법 이름 -> (실행 함수, 난수 사용 여부). 난수를 쓰지 않는 방법은 한 번만 실행한다.
METHODS = {
    "h5": (run_h5, False),
    "csa_f": (csa_f, True),
    "csa_t": (csa_t, True),
    "sa_geo": (lambda inst, rng, budget: sa_t(inst, rng, budget, "geo"), True),
    "sa_log": (lambda inst, rng, budget: sa_t(inst, rng, budget, "log"), True),
    "sa_exp": (lambda inst, rng, budget: sa_t(inst, rng, budget, "exp"), True),
    # 논문과 다르게 읽는 변형. 해석의 영향을 비교할 때에만 --methods로 지정한다
    # pct: GRASP 제한 목록을 미배정 작업의 5%로 읽음, rnd: 수용체 편집을 수락 검사 없는 무작위 이동으로 함
    "csa_f_pct": (lambda inst, rng, budget: csa_f(inst, rng, budget, rcl_percent=True), True),
    "csa_t_pct": (lambda inst, rng, budget: csa_t(inst, rng, budget, rcl_percent=True), True),
    "csa_f_rnd": (lambda inst, rng, budget: csa_f(inst, rng, budget, receptor_random=True), True),
    "csa_t_rnd": (lambda inst, rng, budget: csa_t(inst, rng, budget, receptor_random=True), True),
}
DEFAULT_METHODS = ["h5", "csa_f", "csa_t", "sa_geo", "sa_log", "sa_exp"]

FIELDS = [
    "instance", "size", "n", "m", "setup", "p", "tau", "R", "idx",
    "method", "rep", "seed", "objective", "elapsed", "iterations", "time_limit", "machine",
]


def make_seed(instance, method, rep):
    """실행 환경과 무관하게 같은 값이 나오는 시드."""
    return zlib.crc32(f"{instance}|{method}|{rep}".encode())


def run_instance(task):
    """인스턴스 하나에 대해 요청된 방법과 반복을 모두 실행하고, 결과 행의 목록을 돌려준다."""
    path, methods, reps, scale, tag, done, optimum = task
    path = Path(path)
    inst = load_instance(path)
    limit = time_limit_seconds(inst, scale)
    rows = []
    for method in methods:
        algorithm, stochastic = METHODS[method]
        for rep in range(reps if stochastic else 1):
            if (inst.name, method, rep) in done:
                continue
            seed = make_seed(inst.name, method, rep)
            result = algorithm(inst, random.Random(seed), Budget(time_limit=limit))
            problems = validate(inst, result.schedule)
            assert not problems, (inst.name, method, problems)
            assert result.objective == result.schedule.total
            assert optimum is None or result.objective >= optimum, (inst.name, method, result.objective, optimum)
            rows.append({
                "instance": inst.name, "size": path.parent.name, **parse_name(inst.name),
                "method": method, "rep": rep, "seed": seed, "objective": result.objective,
                "elapsed": round(result.elapsed, 6), "iterations": result.iterations, "time_limit": limit,
                "machine": tag,
            })
    return rows


def known_optima(size):
    """MILP로 구한 최적값이 있으면 읽어 온다. 결과가 최적값보다 작게 나오는 오류를 검사하는 데 사용한다."""
    path = RESULTS_DIR / f"milp_{size}.csv"
    if not path.exists():
        return {}
    with path.open(newline="") as handle:
        return {row["instance"]: int(row["objective"]) for row in csv.DictReader(handle) if row["optimal"] == "True"}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--size", required=True, choices=["small", "medium"])
    parser.add_argument("--methods", default=",".join(DEFAULT_METHODS), help="쉼표로 구분한 방법 이름")
    parser.add_argument("--reps", type=int, default=5, help="난수를 쓰는 방법의 반복 횟수")
    parser.add_argument("--scale", type=float, default=1.0, help="시간 제한에 곱하는 속도 보정 계수 c")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--shard", default="0/1", help="i/k: 인스턴스를 k개 묶음으로 나눈 것 중 i번째만 실행")
    parser.add_argument("--every", type=int, default=1, help="k번째 인스턴스마다 하나씩만 실행(예비 실험용)")
    parser.add_argument("--tag", default=platform.node() or "machine", help="결과 파일 이름과 machine 열에 쓰는 노트북 이름")
    args = parser.parse_args()

    methods = args.methods.split(",")
    unknown = [name for name in methods if name not in METHODS]
    if unknown:
        parser.error(f"알 수 없는 방법: {unknown}")
    part, parts = (int(v) for v in args.shard.split("/"))
    paths = [path for index, path in enumerate(list_instances(args.size)[:: args.every]) if index % parts == part]
    tag = re.sub(r"[^A-Za-z0-9_-]", "_", args.tag)

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"raw_{args.size}_{tag}.csv"
    done = {}
    if out.exists():
        with out.open(newline="") as handle:
            for row in csv.DictReader(handle):
                done.setdefault(row["instance"], set()).add((row["instance"], row["method"], int(row["rep"])))
    optima = known_optima(args.size)
    tasks = [
        (str(path), methods, args.reps, args.scale, tag, done.get(path.stem, set()), optima.get(path.stem))
        for path in paths
    ]

    print(f"{len(tasks)}개 인스턴스, 방법 {methods}, 반복 {args.reps}회, 프로세스 {args.workers}개 -> {out.relative_to(RESULTS_DIR.parent)}")
    write_header = not out.exists()
    with out.open("a", newline="") as handle, Pool(args.workers) as pool:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if write_header:
            writer.writeheader()
        for count, rows in enumerate(pool.imap_unordered(run_instance, tasks), start=1):
            writer.writerows(rows)
            handle.flush()
            if count % 100 == 0 or count == len(tasks):
                print(f"  {count}/{len(tasks)}")


if __name__ == "__main__":
    main()
