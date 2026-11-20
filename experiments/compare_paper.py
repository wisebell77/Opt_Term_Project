"""소규모와 중규모 결과의 ARDI를 논문 Table 2, Table 3(H5, CSA_f, CSA_t 열)과 요인별로 비교한다.

사용 예 (codes 폴더에서 실행):
    python -m experiments.compare_paper --raw results/raw_small_full.csv
    python -m experiments.compare_paper --size medium

소규모의 기준값은 MILP 최적값이다. 중규모는 MILP 결과가 없으므로, 실행한 방법들의 모든 실행 가운데 최선값을 기준값으로 쓴다.
방법은 (MILP,) H5, CSA_f, CSA_t만 있으므로 RDI의 최악값이 논문(19개 방법)과 다르다.
따라서 ARDI의 절대 수치가 아니라 방법의 순서와 요인별 경향, 그리고 H5에 대한 비율을 비교한다.
"""
from __future__ import annotations

import argparse
import csv
import statistics as st
from collections import defaultdict

from src.instance import RESULTS_DIR, parse_name

METHODS = ["h5", "csa_f", "csa_t"]
# 논문의 ARDI: (H5, CSA_f, CSA_t). small은 Table 2, medium은 Table 3이다.
# Table 2는 τ와 R의 행 이름이 서로 바뀌어 인쇄되어 있다. 값의 크기, Table 3, 8.1절의 서술("τ = 0.2에서 H5와 CSA_f는
# 차이가 없다")로 판단하여 아래에는 바로잡은 값을 적었다.
PAPER = {
    "small": {
        "Total": (5.687, 6.888, 2.088),
        ("n", 6): (6.381, 10.339, 2.392), ("n", 8): (6.114, 8.294, 2.394),
        ("n", 10): (5.420, 5.201, 2.052), ("n", 12): (4.834, 3.716, 1.512),
        ("m", 2): (7.346, 2.977, 1.746), ("m", 3): (5.068, 5.119, 1.858),
        ("m", 4): (5.695, 9.225, 2.496), ("m", 5): (4.638, 10.231, 2.250),
        ("p", 50): (4.201, 5.972, 1.538), ("p", 80): (5.204, 6.951, 1.922), ("p", 100): (7.656, 7.741, 2.804),
        ("setup", 49): (6.697, 8.362, 2.275), ("setup", 124): (4.677, 5.413, 1.900),
        ("tau", 0.2): (2.725, 2.831, 0.837), ("tau", 0.4): (8.650, 10.944, 3.338),
        ("R", 0.2): (5.354, 7.180, 1.994), ("R", 0.4): (6.020, 6.596, 2.181),
    },
    "medium": {
        "Total": (1.645, 1.416, 0.338),
        ("n", 15): (3.485, 4.735, 1.239), ("n", 20): (2.400, 2.334, 0.521), ("n", 25): (1.607, 1.028, 0.223),
        ("n", 30): (0.979, 0.235, 0.030), ("n", 35): (0.766, 0.071, 0.008), ("n", 40): (0.632, 0.091, 0.007),
        ("m", 2): (1.023, 0.188, 0.111), ("m", 4): (1.854, 0.966, 0.247),
        ("m", 6): (2.118, 1.818, 0.566), ("m", 8): (1.583, 2.691, 0.428),
        ("p", 50): (0.870, 0.791, 0.182), ("p", 80): (1.590, 1.469, 0.329), ("p", 100): (2.474, 1.987, 0.503),
        ("setup", 49): (2.343, 1.983, 0.433), ("setup", 124): (0.946, 0.849, 0.243),
        ("tau", 0.2): (0.566, 0.293, 0.078), ("tau", 0.4): (2.724, 2.539, 0.598),
        ("R", 0.2): (1.340, 1.424, 0.290), ("R", 0.4): (1.950, 1.407, 0.386),
    },
}


def load(raw_path, milp_path=None):
    """실행 기록을 인스턴스별로 묶는다. milp_path가 없으면 기준값은 모든 실행의 최선값이다."""
    optimum = {}
    if milp_path:
        optimum = {r["instance"]: int(float(r["objective"])) for r in csv.DictReader(open(milp_path, newline=""))}
    values = defaultdict(lambda: defaultdict(list))
    elapsed = defaultdict(list)
    for r in csv.DictReader(open(raw_path, newline="")):
        values[r["instance"]][r["method"]].append(int(r["objective"]))
        elapsed[r["method"]].append(float(r["elapsed"]))
    rows = []
    for name, per_method in values.items():
        v = {m: sum(x) / len(x) for m, x in per_method.items()}
        if optimum:
            v["milp"] = reference = optimum[name]
        else:
            reference = min(min(x) for x in per_method.values())
        best, worst = min(v.values()), max(v.values())
        rdi = {m: 100 * (x - best) / (worst - best) if worst > best else 0.0 for m, x in v.items()}
        rows.append({"factors": parse_name(name), "v": v, "rdi": rdi, "opt": reference})
    return rows, elapsed


def ardi(rows):
    return [st.mean(r["rdi"][m] for r in rows) for m in METHODS]


def ratio(value, base):
    return value / base if base else float("nan")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--size", default="small", choices=["small", "medium"])
    parser.add_argument("--raw", default=None, help="실행 기록 파일(기본값은 results/raw_<크기>_full.csv)")
    parser.add_argument("--milp", default=None, help="MILP 결과 파일(기본값은 results/milp_<크기>.csv가 있으면 그 파일)")
    args = parser.parse_args()
    raw = args.raw or str(RESULTS_DIR / f"raw_{args.size}_full.csv")
    default_milp = RESULTS_DIR / f"milp_{args.size}.csv"
    milp = args.milp or (str(default_milp) if default_milp.exists() else None)
    rows, elapsed = load(raw, milp)
    reference = "최적값" if milp else "기준값(실행한 방법들의 최선값)"

    print(f"인스턴스 {len(rows)}개, {reference}이 0인 인스턴스 {sum(r['opt'] == 0 for r in rows)}개")
    print(f"{'수준':10s} | 우리 H5     CSA_f  CSA_t | 논문 H5     CSA_f  CSA_t | 우리 f/H5 t/H5 | 논문 f/H5 t/H5")
    for key, paper in PAPER[args.size].items():
        sel = rows if key == "Total" else [r for r in rows if r["factors"][key[0]] == key[1]]
        if not sel:  # 일부 인스턴스만 실행한 경우 해당 수준이 없을 수 있다
            continue
        ours = ardi(sel)
        label = "Total" if key == "Total" else f"{key[0]}={key[1]}"
        print(f"{label:10s} | {ours[0]:8.2f} {ours[1]:6.2f} {ours[2]:6.2f} | {paper[0]:8.3f} {paper[1]:6.3f} {paper[2]:6.3f} | "
              f"{ratio(ours[1], ours[0]):6.2f} {ratio(ours[2], ours[0]):5.2f} | {paper[1] / paper[0]:6.2f} {paper[2] / paper[0]:5.2f}")

    print(f"\n{reference} 도달 비율과 평균 실행 시간(초)")
    for m in METHODS:
        hit = sum(r["v"][m] == r["opt"] for r in rows) / len(rows)
        print(f"  {m:6s} {100 * hit:5.1f}%  {st.mean(elapsed[m]):.3f}")
    positive = [r for r in rows if r["opt"] > 0]
    if positive:
        print(f"RPD({reference} > 0인 {len(positive)}개, %): " + ", ".join(
            f"{m} {st.mean(100 * (r['v'][m] - r['opt']) / r['opt'] for r in positive):.1f}" for m in METHODS))
    t_better = sum(r["v"]["csa_t"] < r["v"]["csa_f"] for r in rows)
    f_better = sum(r["v"]["csa_t"] > r["v"]["csa_f"] for r in rows)
    print(f"CSA_t 대 CSA_f: CSA_t 우세 {t_better}, 동률 {len(rows) - t_better - f_better}, CSA_f 우세 {f_better}")
    print(f"CSA_f가 H5보다 나은 인스턴스 {sum(r['v']['csa_f'] < r['v']['h5'] for r in rows)}개, "
          f"나쁜 인스턴스 {sum(r['v']['csa_f'] > r['v']['h5'] for r in rows)}개")


if __name__ == "__main__":
    main()
