"""MILP로 인스턴스의 최적값을 구하여 results/milp_<크기>.csv에 기록한다.

사용 예 (codes 폴더에서 실행):
    python -m experiments.run_milp --size small

중단한 뒤 같은 명령을 다시 실행하면 끝난 인스턴스는 건너뛴다.
"""
from __future__ import annotations

import argparse
import csv
import os
from multiprocessing import Pool

from src.instance import RESULTS_DIR, list_instances, load_instance
from src.milp import solve_milp

FIELDS = ["instance", "objective", "optimal", "bound", "runtime"]


def solve(task):
    path, time_limit = task
    inst = load_instance(path)
    result = solve_milp(inst, time_limit)
    return {
        "instance": inst.name, "objective": result["objective"], "optimal": result["optimal"],
        "bound": round(result["bound"], 4), "runtime": round(result["runtime"], 4),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--size", default="small", choices=["small", "medium"])
    parser.add_argument("--time-limit", type=float, default=100.0, help="인스턴스당 시간 제한(초)")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--every", type=int, default=1, help="k번째 인스턴스마다 하나씩만 실행")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"milp_{args.size}.csv"
    done = set()
    if out.exists():
        with out.open(newline="") as handle:
            done = {row["instance"] for row in csv.DictReader(handle)}
    tasks = [(str(path), args.time_limit) for path in list_instances(args.size)[:: args.every] if path.stem not in done]

    print(f"{len(tasks)}개 인스턴스 -> {out.relative_to(RESULTS_DIR.parent)}")
    write_header = not out.exists()
    with out.open("a", newline="") as handle, Pool(args.workers) as pool:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if write_header:
            writer.writeheader()
        for count, row in enumerate(pool.imap_unordered(solve, tasks), start=1):
            writer.writerow(row)
            handle.flush()
            if count % 200 == 0 or count == len(tasks):
                print(f"  {count}/{len(tasks)}")


if __name__ == "__main__":
    main()
