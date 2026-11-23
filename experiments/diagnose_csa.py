"""CSA 진단: 수용체 편집 방식과 동점 처리 기준에 따라 기억 집합과 클론이 얼마나 다양한지 측정한다.

사용 예 (codes 폴더에서 실행):
    python -m experiments.diagnose_csa --workers 4

대상은 최적값이 양수이고 작업이 기계 사이를 이동할 수 있는 소규모 인스턴스이다. CSA_t를 수용체 편집 2종
(improve: 논문의 개선형 연산자, rnd: 수락 검사 없는 무작위 이동)과 동점 처리 기준 2종(first, random)으로
본 실험과 같은 시간 제한에서 실행하고, 세대마다 다음을 기록하여 results/diagnostics/csa_diversity_small.csv에 쓴다.

    memory:   기억 집합(20개) 안의 서로 다른 해의 수
    clones:   클론(60개) 가운데 서로 다른 해의 수
    same:     부모와 같은 해로 끝난 클론의 비율
    improved: 부모보다 좋아진 클론의 비율

results/raw_small_full.csv가 있으면, 작업이 기계 사이를 이동할 수 없는 인스턴스와 나머지를 나누어
방법별로 최적값을 놓친 실행의 비율도 출력한다.
"""
from __future__ import annotations

import argparse
import csv
import random
import statistics as st
from collections import defaultdict
from multiprocessing import Pool

from experiments.run import make_seed
from src import tiebreak
from src.budget import Budget, time_limit_seconds
from src.csa import csa_t
from src.instance import DATA_DIR, RESULTS_DIR, list_instances, load_instance

RECEPTORS = ("improve", "rnd")
TIES = ("first", "random")
FIELDS = ["instance", "receptor", "tie", "rep", "opt", "objective", "generations", "memory", "clones", "same", "improved"]


def shape(sched):
    return tuple(map(tuple, sched.seqs))


def movable(inst):
    """적격 기계가 2대 이상인 작업이 하나라도 있으면 True이다."""
    return any(len(machines) > 1 for machines in inst.elig)


class Diversity:
    """csa의 observe로 넘겨, 세대마다 (memory, clones, same, improved)를 모은다."""

    def __init__(self):
        self.rows = []

    def __call__(self, cells, parents, clones):
        pairs = list(zip(parents, clones))
        same = sum(clone.sched.seqs == parent.sched.seqs for parent, clone in pairs)
        improved = sum(clone.sched.total < parent.sched.total for parent, clone in pairs)
        self.rows.append((
            len({shape(cell.sched) for cell in cells}), len({shape(cell.sched) for cell in clones}),
            same / len(pairs), improved / len(pairs),
        ))

    def means(self):
        """세대에 대한 평균. 세대를 한 번도 수행하지 않았으면 모두 0이다."""
        return [st.mean(column) for column in zip(*self.rows)] if self.rows else [0, 0, 0, 0]


def run(task):
    name, opt, receptor, tie, rep = task
    inst = load_instance(DATA_DIR / "small" / f"{name}.txt")
    rng = random.Random(make_seed(name, f"diversity_{receptor}_{tie}", rep))
    seen = Diversity()
    with tiebreak.policy(tie, rng):
        result = csa_t(inst, rng, Budget(time_limit=time_limit_seconds(inst)), receptor_random=receptor == "rnd", observe=seen)
    return [name, receptor, tie, rep, opt, result.objective, result.iterations] + seen.means()


def optima():
    with (RESULTS_DIR / "milp_small.csv").open(newline="") as handle:
        return {row["instance"]: int(float(row["objective"])) for row in csv.DictReader(handle)}


def miss_rates_by_type(raw_path, optimum):
    """{방법: (이동할 수 없는 인스턴스에서 놓친 실행의 비율, 나머지 인스턴스에서의 비율)} (%)."""
    fixed = {path.stem for path in list_instances("small") if not movable(load_instance(path))}
    count = defaultdict(lambda: [0, 0, 0, 0])  # 방법 -> [고정 실행 수, 고정에서 놓침, 나머지 실행 수, 나머지에서 놓침]
    with open(raw_path, newline="") as handle:
        for row in csv.DictReader(handle):
            offset = 0 if row["instance"] in fixed else 2
            count[row["method"]][offset] += 1
            count[row["method"]][offset + 1] += int(row["objective"]) != optimum[row["instance"]]
    return len(fixed), {m: (100 * c[1] / c[0], 100 * c[3] / c[2]) for m, c in count.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--every", type=int, default=1, help="k번째 인스턴스마다 하나씩만 실행(시험용)")
    args = parser.parse_args()

    optimum = optima()
    names = [path.stem for path in list_instances("small") if optimum[path.stem] > 0 and movable(load_instance(path))][:: args.every]
    tasks = [(name, optimum[name], receptor, tie, rep)
             for name in names for receptor in RECEPTORS for tie in TIES for rep in range(args.reps)]
    with Pool(args.workers) as pool:
        rows = pool.map(run, tasks, chunksize=4)
    out = RESULTS_DIR / "diagnostics" / "csa_diversity_small.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(FIELDS)
        writer.writerows(rows)

    print(f"최적값이 양수이고 작업이 기계 사이를 이동할 수 있는 소규모 인스턴스 {len(names)}개, 반복 {args.reps}회 -> {out.relative_to(RESULTS_DIR.parent)}")
    print("수용체 편집  동점    | 최적 도달(%)  세대 수  기억 집합의 서로 다른 해  클론의 서로 다른 해  부모와 같은 클론(%)  좋아진 클론(%)")
    for receptor in RECEPTORS:
        for tie in TIES:
            part = [row for row in rows if (row[1], row[2]) == (receptor, tie)]
            print(f"{receptor:10s} {tie:7s} | {100 * st.mean(row[5] == row[4] for row in part):10.1f} {st.mean(row[6] for row in part):8.1f} "
                  f"{st.mean(row[7] for row in part):14.2f} {st.mean(row[8] for row in part):18.2f} "
                  f"{100 * st.mean(row[9] for row in part):16.1f} {100 * st.mean(row[10] for row in part):14.2f}")

    raw = RESULTS_DIR / "raw_small_full.csv"
    if raw.exists():
        fixed, rates = miss_rates_by_type(raw, optimum)
        print(f"\n최적값을 놓친 실행의 비율(%): 작업이 기계 사이를 이동할 수 없는 인스턴스 {fixed}개 / 나머지")
        for method, (fixed_rate, other_rate) in rates.items():
            print(f"  {method:12s} {fixed_rate:6.2f} / {other_rate:6.2f}")


if __name__ == "__main__":
    main()
