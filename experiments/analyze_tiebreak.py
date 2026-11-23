"""동점 처리 기준 실험의 집계: 기준(first, last, csum, random)별로 H5, CSA_f, CSA_t의 지표를 비교한다.
같은 파일에 SA_t(기준 random)의 실행 기록이 있으면, 냉각 방식 3종과 CSA_t의 비교도 함께 출력한다.

사용 예 (codes 폴더에서 실행):
    python -m experiments.run --size small --methods tiebreak --reps 3 --workers 4 --out results/tiebreak/raw_small.csv
    python -m experiments.run --size small --methods sa_geo_random,sa_log_random,sa_exp_random --reps 3 --workers 4 --out results/tiebreak/raw_small.csv
    python -m experiments.analyze_tiebreak --size small
    python -m experiments.analyze_tiebreak --size medium --raw results/tiebreak/raw_medium.csv results/raw_medium_full.csv

기준의 뜻은 src/tiebreak.py에 있다. 기준값은 MILP 결과(results/milp_<크기>.csv)가 있으면 최적값이고,
없으면 모든 기준의 모든 실행 가운데 최선값이다.
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics as st
from collections import defaultdict
from math import comb

from src import tiebreak
from src.insertion import best_position_total, insert
from src.instance import RESULTS_DIR, list_instances, load_instance, parse_name
from src.schedule import Schedule

BASES = ("h5", "csa_f", "csa_t", "sa_geo", "sa_log", "sa_exp")
SA = ("sa_geo", "sa_log", "sa_exp")
FACTORS = ("tau", "n", "m")


def split(method):
    """방법 이름을 (방법, 기준)으로 나눈다. 이름에 기준이 없으면 first이고, 집계의 대상이 아니면 None이다."""
    if method in BASES:
        return method, "first"
    base, _, mode = method.rpartition("_")
    return (base, mode) if base in BASES and mode in tiebreak.MODES[1:] else None


def load(raw_path, milp_path=None):
    """실행 기록을 {인스턴스: {"opt": 기준값, "runs": {(기준, 방법): [목적함수값]}, "iters": {(기준, 방법): [반복 횟수]}}}로 묶는다.

    raw_path는 파일 하나 또는 파일의 목록이다."""
    runs = defaultdict(lambda: defaultdict(list))
    iters = defaultdict(lambda: defaultdict(list))
    for path in [raw_path] if isinstance(raw_path, (str, os.PathLike)) else raw_path:
        with open(path, newline="") as handle:
            for row in csv.DictReader(handle):
                found = split(row["method"])
                if found:
                    key = (found[1], found[0])
                    runs[row["instance"]][key].append(int(row["objective"]))
                    iters[row["instance"]][key].append(int(row["iterations"]))
    optimum = {}
    if milp_path:
        with open(milp_path, newline="") as handle:
            optimum = {row["instance"]: int(float(row["objective"])) for row in csv.DictReader(handle)}
    return {
        name: {
            "opt": optimum[name] if optimum else min(min(values) for values in per_key.values()),
            "runs": dict(per_key),
            "iters": dict(iters[name]),
        }
        for name, per_key in runs.items()
    }


def summarize(data):
    """(기준, 방법)별 지표.

    hit: 기준값에 도달한 실행의 비율(%), mean: 인스턴스별 평균 총 지연의 평균, rpd: 기준값이 양수인 인스턴스의 평균 RPD(%),
    missed: 평균이 기준값보다 큰 인스턴스의 수, unstable: 반복 사이에 값이 달라진 인스턴스의 수,
    gens: 기준값이 양수인 인스턴스에서의 평균 반복 횟수(CSA는 세대 수, SA는 이웃 해 평가 횟수)."""
    out = {}
    for key in sorted({key for entry in data.values() for key in entry["runs"]}):
        hits = total = missed = unstable = 0
        means, rpds, gens = [], [], []
        for entry in data.values():
            values = entry["runs"].get(key)
            if not values:
                continue
            opt, mean = entry["opt"], sum(values) / len(values)
            hits += sum(value == opt for value in values)
            total += len(values)
            means.append(mean)
            missed += mean > opt
            unstable += min(values) != max(values)
            if opt > 0:
                rpds.append(100 * (mean - opt) / opt)
                gens += entry["iters"][key]
        out[key] = {
            "hit": 100 * hits / total, "mean": st.mean(means), "rpd": st.mean(rpds) if rpds else float("nan"),
            "missed": missed, "unstable": unstable, "gens": st.mean(gens) if gens else float("nan"),
        }
    return out


def compare(data, first, second):
    """인스턴스별 평균 총 지연을 비교하여, second가 first보다 (더 좋은, 같은, 더 나쁜) 인스턴스의 수를 돌려준다.

    first와 second는 (기준, 방법)이다."""
    better = same = worse = 0
    for entry in data.values():
        a, b = entry["runs"].get(first), entry["runs"].get(second)
        if not a or not b:
            continue
        diff = sum(b) / len(b) - sum(a) / len(a)
        better, same, worse = better + (diff < 0), same + (diff == 0), worse + (diff > 0)
    return better, same, worse


def against_first(data, base, mode):
    """인스턴스별 평균 총 지연을 기준 first와 비교한 (더 좋은, 같은, 더 나쁜) 인스턴스의 수."""
    return compare(data, ("first", base), (mode, base))


def sign_test(better, worse):
    """양측 부호 검정의 p값. 두 기준에 차이가 없다면 더 좋은 인스턴스와 더 나쁜 인스턴스가 같은 확률로 나온다."""
    count, larger = better + worse, max(better, worse)
    if count == 0:
        return 1.0
    return min(1.0, 2 * sum(comb(count, k) for k in range(larger, count + 1)) / 2**count)


def h5_decisions(inst):
    """H5의 구성 단계를 기준 first로 따라가며, 삽입 결정마다 (작업, {기준: (기계, 위치)})를 내놓는다."""
    sched = Schedule.empty(inst)
    for j in sorted(range(inst.n), key=lambda j: (len(inst.elig[j]), inst.d[j], j)):  # h5.construct와 같은 순서
        picks = {}
        for mode in ("first", "last", "csum"):
            with tiebreak.policy(mode):
                picks[mode] = best_position_total(inst, sched, j)
        yield j, picks
        insert(inst, sched, *picks["first"], j)


def decision_ties(inst):
    """H5 구성 단계의 (삽입 결정 수, 기준 last에서 선택이 달라지는 결정 수, 기준 csum에서 달라지는 결정 수)."""
    decisions = differ_last = differ_csum = 0
    for _, picks in h5_decisions(inst):
        decisions += 1
        differ_last += picks["last"] != picks["first"]
        differ_csum += picks["csum"] != picks["first"]
    return decisions, differ_last, differ_csum


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--size", default="small", choices=["small", "medium"])
    parser.add_argument("--raw", nargs="+", default=None, help="실행 기록 파일. 여러 개를 적을 수 있다(기본값은 results/tiebreak/raw_<크기>.csv)")
    parser.add_argument("--milp", default=None, help="MILP 결과 파일(기본값은 results/milp_<크기>.csv가 있으면 그 파일)")
    args = parser.parse_args()
    raw = args.raw or [str(RESULTS_DIR / "tiebreak" / f"raw_{args.size}.csv")]
    default_milp = RESULTS_DIR / f"milp_{args.size}.csv"
    milp = args.milp or (str(default_milp) if default_milp.exists() else None)
    data = load(raw, milp)
    summary = summarize(data)
    reference = "최적값" if milp else "기준값(모든 실행의 최선값)"
    positive = sum(entry["opt"] > 0 for entry in data.values())
    print(f"인스턴스 {len(data)}개, {reference}이 양수인 인스턴스 {positive}개")

    print(f"\n[1] 기준별 지표 ({reference} 기준)")
    print(f"{'방법':6s} {'기준':7s} | 도달(%)  평균 지연  RPD(%)  놓친 인스턴스  반복 간 차이  평균 반복 수")
    for base in BASES:
        for mode in tiebreak.MODES:
            row = summary.get((mode, base))
            if row:
                print(f"{base:6s} {mode:7s} | {row['hit']:7.2f} {row['mean']:10.3f} {row['rpd']:7.2f} "
                      f"{row['missed']:13d} {row['unstable']:12d} {row['gens']:12.1f}")

    print("\n[2] 기준 first와의 인스턴스별 비교 (더 좋음 / 같음 / 더 나쁨, 괄호는 부호 검정의 p값)")
    for base in BASES:
        if ("first", base) not in summary:
            continue
        cells = []
        for mode in tiebreak.MODES[1:]:
            if (mode, base) in summary:
                better, same, worse = against_first(data, base, mode)
                cells.append(f"{mode} {better}/{same}/{worse} (p={sign_test(better, worse):.3g})")
        print(f"{base:6s} | " + "   ".join(cells))

    print(f"\n[3] 요인별 {reference} 도달 비율(%)")
    factors = {name: parse_name(name) for name in data}
    for factor in FACTORS:
        for level in sorted({f[factor] for f in factors.values()}):
            part = summarize({name: entry for name, entry in data.items() if factors[name][factor] == level})
            cells = [f"{base} " + " ".join(f"{part[(mode, base)]['hit']:6.2f}" for mode in tiebreak.MODES if (mode, base) in part)
                     for base in BASES if any(key[1] == base for key in part)]
            print(f"{factor}={level!s:5s} | " + "   ".join(cells))
    print("  (방법마다 실행한 기준을 " + ", ".join(tiebreak.MODES) + "의 순서로 표시)")

    print("\n[4] H5 구성 단계의 삽입 결정 가운데 기준에 따라 선택이 달라지는 비율(%)")
    counts = defaultdict(lambda: [0, 0, 0])
    for path in list_instances(args.size):
        if path.stem in data:
            result = decision_ties(load_instance(path))
            for group in ("전체", f"tau={factors[path.stem]['tau']}"):
                counts[group] = [a + b for a, b in zip(counts[group], result)]
    for group, (decisions, differ_last, differ_csum) in sorted(counts.items()):
        print(f"{group:8s} | 결정 {decisions:6d}개, first와 last가 다른 결정 {100 * differ_last / decisions:5.1f}%, "
              f"first와 csum이 다른 결정 {100 * differ_csum / decisions:5.1f}%")

    if any(("random", base) in summary for base in SA):
        print("\n[5] 기준 random에서의 방법 비교 (오른쪽 방법이 더 좋음 / 같음 / 더 나쁨, 괄호는 부호 검정의 p값)")
        pairs = [("csa_t", base) for base in SA] + [("sa_geo", "sa_log"), ("sa_geo", "sa_exp"), ("sa_log", "sa_exp")]
        for first, second in pairs:
            if ("random", first) in summary and ("random", second) in summary:
                better, same, worse = compare(data, ("random", first), ("random", second))
                print(f"{first:6s} 대 {second:6s} | {better}/{same}/{worse} (p={sign_test(better, worse):.3g})")


if __name__ == "__main__":
    main()
