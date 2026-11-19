"""소규모 결과의 ARDI를 논문 Table 2(H5, CSA_f, CSA_t 열)와 요인별로 비교한다.

사용 예 (codes 폴더에서 실행):
    python -m experiments.compare_paper --raw results/raw_small_full.csv

기준값은 MILP 최적값이고, 방법은 MILP, H5, CSA_f, CSA_t만 있으므로 RDI의 최악값이 논문(19개 방법)과 다르다.
따라서 ARDI의 절대 수치가 아니라 방법의 순서와 요인별 경향, 그리고 H5에 대한 비율을 비교한다.
"""
from __future__ import annotations

import argparse
import csv
import statistics as st
from collections import defaultdict

from src.instance import RESULTS_DIR, parse_name

METHODS = ["h5", "csa_f", "csa_t"]
# 논문 Table 2: (H5, CSA_f, CSA_t)
PAPER = {
    "Total": (5.687, 6.888, 2.088),
    ("n", 6): (6.381, 10.339, 2.392), ("n", 8): (6.114, 8.294, 2.394),
    ("n", 10): (5.420, 5.201, 2.052), ("n", 12): (4.834, 3.716, 1.512),
    ("m", 2): (7.346, 2.977, 1.746), ("m", 3): (5.068, 5.119, 1.858),
    ("m", 4): (5.695, 9.225, 2.496), ("m", 5): (4.638, 10.231, 2.250),
    ("p", 50): (4.201, 5.972, 1.538), ("p", 80): (5.204, 6.951, 1.922), ("p", 100): (7.656, 7.741, 2.804),
    ("setup", 49): (6.697, 8.362, 2.275), ("setup", 124): (4.677, 5.413, 1.900),
    ("tau", 0.2): (2.725, 2.831, 0.837), ("tau", 0.4): (8.650, 10.944, 3.338),
    ("R", 0.2): (5.354, 7.180, 1.994), ("R", 0.4): (6.020, 6.596, 2.181),
}


def load(raw_path, milp_path):
    optimum = {r["instance"]: int(float(r["objective"])) for r in csv.DictReader(open(milp_path, newline=""))}
    values = defaultdict(lambda: defaultdict(list))
    elapsed = defaultdict(list)
    for r in csv.DictReader(open(raw_path, newline="")):
        values[r["instance"]][r["method"]].append(int(r["objective"]))
        elapsed[r["method"]].append(float(r["elapsed"]))
    rows = []
    for name, per_method in values.items():
        v = {m: sum(x) / len(x) for m, x in per_method.items()}
        v["milp"] = optimum[name]
        best, worst = min(v.values()), max(v.values())
        rdi = {m: 100 * (x - best) / (worst - best) if worst > best else 0.0 for m, x in v.items()}
        rows.append({"factors": parse_name(name), "v": v, "rdi": rdi, "opt": optimum[name]})
    return rows, elapsed


def ardi(rows):
    return [st.mean(r["rdi"][m] for r in rows) for m in METHODS]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw", default=str(RESULTS_DIR / "raw_small_full.csv"))
    parser.add_argument("--milp", default=str(RESULTS_DIR / "milp_small.csv"))
    args = parser.parse_args()
    rows, elapsed = load(args.raw, args.milp)

    print(f"인스턴스 {len(rows)}개, 최적값이 0인 인스턴스 {sum(r['opt'] == 0 for r in rows)}개")
    print(f"{'수준':10s} | 우리 H5     CSA_f  CSA_t | 논문 H5     CSA_f  CSA_t | 우리 f/H5 t/H5 | 논문 f/H5 t/H5")
    for key, paper in PAPER.items():
        sel = rows if key == "Total" else [r for r in rows if r["factors"][key[0]] == key[1]]
        ours = ardi(sel)
        label = "Total" if key == "Total" else f"{key[0]}={key[1]}"
        print(f"{label:10s} | {ours[0]:8.2f} {ours[1]:6.2f} {ours[2]:6.2f} | {paper[0]:8.3f} {paper[1]:6.3f} {paper[2]:6.3f} | "
              f"{ours[1] / ours[0]:6.2f} {ours[2] / ours[0]:5.2f} | {paper[1] / paper[0]:6.2f} {paper[2] / paper[0]:5.2f}")

    print("\n최적 도달 비율과 평균 실행 시간(초)")
    for m in METHODS:
        hit = sum(r["v"][m] == r["opt"] for r in rows) / len(rows)
        print(f"  {m:6s} {100 * hit:5.1f}%  {st.mean(elapsed[m]):.3f}")
    positive = [r for r in rows if r["opt"] > 0]
    print("RPD(최적값 > 0, %): " + ", ".join(
        f"{m} {st.mean(100 * (r['v'][m] - r['opt']) / r['opt'] for r in positive):.1f}" for m in METHODS))
    t_better = sum(r["v"]["csa_t"] < r["v"]["csa_f"] for r in rows)
    f_better = sum(r["v"]["csa_t"] > r["v"]["csa_f"] for r in rows)
    print(f"CSA_t 대 CSA_f: CSA_t 우세 {t_better}, 동률 {len(rows) - t_better - f_better}, CSA_f 우세 {f_better}")
    print(f"CSA_f가 H5보다 나은 인스턴스 {sum(r['v']['csa_f'] < r['v']['h5'] for r in rows)}개, "
          f"나쁜 인스턴스 {sum(r['v']['csa_f'] > r['v']['h5'] for r in rows)}개")


if __name__ == "__main__":
    main()
