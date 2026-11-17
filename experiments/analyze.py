"""실험 결과 집계: results/raw_*.csv와 results/milp_*.csv를 읽어 지표를 계산한다.

사용 예 (codes 폴더에서 실행):
    python -m experiments.analyze

기준값은 소규모에서는 MILP의 최적값이고, MILP 결과가 없는 인스턴스(중규모)에서는 실행한 모든
방법이 찾은 최선값이다. 기준값이 0인 인스턴스는 RPD를 정의할 수 없으므로 절대 차이로 따로 집계한다.
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from src.instance import RESULTS_DIR

FACTORS = ["n", "m", "setup", "p", "tau", "R"]


def instance_table(runs, ref):
    """(인스턴스, 방법)별 지표 표를 만든다.

    runs: instance, method, rep, objective 열이 있는 실행 기록. ref: 인스턴스별 기준값(Series).
    결과 열: mean_obj(반복 평균), ref, gap(평균 - 기준값), rpd(%), rdi(%), hit(기준값에 도달한 실행의 비율).
    """
    grouped = runs.groupby(["instance", "method"])["objective"]
    table = grouped.mean().rename("mean_obj").reset_index()
    table["ref"] = table["instance"].map(ref)
    table["gap"] = table["mean_obj"] - table["ref"]
    table["rpd"] = np.where(table["ref"] > 0, 100 * table["gap"] / table["ref"].where(table["ref"] > 0), np.nan)
    best = table.groupby("instance")["mean_obj"].transform("min")
    worst = table.groupby("instance")["mean_obj"].transform("max")
    table["rdi"] = np.where(worst > best, 100 * (table["mean_obj"] - best) / (worst - best).where(worst > best), 0.0)
    reached = (runs["objective"] == runs["instance"].map(ref)).groupby([runs["instance"], runs["method"]]).mean()
    table["hit"] = reached.reindex(pd.MultiIndex.from_frame(table[["instance", "method"]])).to_numpy()
    return table


def method_summary(table):
    """방법별 요약: 기준값이 양수인 인스턴스의 평균 RPD와 기준값이 0인 인스턴스의 평균 절대 차이를 나누어 보고한다."""
    rows = []
    for method, part in table.groupby("method", sort=False):
        zero = part["ref"] == 0
        rows.append({
            "method": method,
            "instances": len(part),
            "ref_zero": int(zero.sum()),
            "mean_obj": part["mean_obj"].mean(),
            "rpd_mean": part.loc[~zero, "rpd"].mean(),
            "gap0_mean": part.loc[zero, "gap"].mean(),
            "rdi_mean": part["rdi"].mean(),
            "hit_rate": part["hit"].mean(),
        })
    return pd.DataFrame(rows)


def compare(table, first, second):
    """두 방법의 인스턴스별 평균 목적함수값을 짝지어 비교한다(승, 무, 패와 Wilcoxon 부호순위 검정)."""
    from scipy.stats import wilcoxon

    wide = table.pivot(index="instance", columns="method", values="mean_obj")[[first, second]].dropna()
    diff = wide[first] - wide[second]
    p_value = wilcoxon(diff[diff != 0]).pvalue if (diff != 0).sum() > 0 else float("nan")
    return {
        "first": first, "second": second, "instances": len(diff),
        "first_better": int((diff < 0).sum()), "ties": int((diff == 0).sum()), "second_better": int((diff > 0).sum()),
        "p_value": p_value,
    }


def load_runs():
    files = sorted(RESULTS_DIR.glob("raw_*.csv"))
    if not files:
        raise SystemExit("results 폴더에 raw_*.csv가 없습니다. 먼저 python -m experiments.run 을 실행하십시오.")
    runs = pd.concat([pd.read_csv(path) for path in files], ignore_index=True)
    return runs.drop_duplicates(subset=["instance", "method", "rep"])


def load_optima(size):
    path = RESULTS_DIR / f"milp_{size}.csv"
    if not path.exists():
        return pd.DataFrame(columns=["instance", "objective", "optimal"])
    return pd.read_csv(path)


def analyze_size(runs, size, pair):
    runs = runs[runs["size"] == size]
    optima = load_optima(size)
    optimal = optima[optima["optimal"].astype(str) == "True"]
    # MILP도 하나의 방법으로 표에 넣고(논문과 동일), 최적값을 기준값으로 사용한다
    milp_rows = optimal[optimal["instance"].isin(runs["instance"])].assign(method="milp", rep=0)
    everything = runs[["instance", "method", "rep", "objective"]]
    if len(milp_rows):
        everything = pd.concat([everything, milp_rows[["instance", "method", "rep", "objective"]]], ignore_index=True)
    ref = everything.groupby("instance")["objective"].min()
    table = instance_table(everything, ref)
    factors = runs.drop_duplicates("instance").set_index("instance")[FACTORS]
    table = table.join(factors, on="instance")

    summary = method_summary(table)
    elapsed = runs.groupby("method")["elapsed"].mean().rename("elapsed_mean")
    summary = summary.join(elapsed, on="method")
    summary.to_csv(RESULTS_DIR / f"summary_{size}.csv", index=False)

    by_factor = []
    for factor in FACTORS:
        for (level, method), part in table.groupby([factor, "method"], sort=True):
            zero = part["ref"] == 0
            by_factor.append({
                "factor": factor, "level": level, "method": method, "instances": len(part),
                "rpd_mean": part.loc[~zero, "rpd"].mean(), "gap0_mean": part.loc[zero, "gap"].mean(),
                "rdi_mean": part["rdi"].mean(), "hit_rate": part["hit"].mean(),
            })
    pd.DataFrame(by_factor).to_csv(RESULTS_DIR / f"factors_{size}.csv", index=False)
    table.to_csv(RESULTS_DIR / f"instances_{size}.csv", index=False)

    source = "MILP 최적값" if len(milp_rows) else "실행한 방법들의 최선값"
    print(f"\n== {size}: 인스턴스 {table['instance'].nunique()}개, 기준값은 {source}")
    print(summary.round(3).to_string(index=False))
    if set(pair) <= set(table["method"]):
        result = compare(table, *pair)
        print(f"  {pair[0]} 대 {pair[1]}: {pair[0]} 우세 {result['first_better']}, 동률 {result['ties']}, "
              f"{pair[1]} 우세 {result['second_better']}, Wilcoxon p = {result['p_value']:.4g}")
        return summary, result
    return summary, None


def plot(summaries):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, len(summaries), figsize=(5.5 * len(summaries), 3.6), squeeze=False)
    for axis, (size, summary) in zip(axes[0], summaries.items()):
        axis.bar(summary["method"], summary["rdi_mean"], color="0.35")
        axis.set_title(f"{size} instances")
        axis.set_ylabel("Average RDI (%)")
        axis.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "fig_rdi.png", dpi=200)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pair", default="csa_t,sa_geo", help="짝지어 비교할 두 방법")
    args = parser.parse_args()
    pair = args.pair.split(",")

    runs = load_runs()
    summaries, tests = {}, []
    for size in ("small", "medium"):
        if (runs["size"] == size).any():
            summary, test = analyze_size(runs, size, pair)
            summaries[size] = summary
            if test:
                tests.append({"size": size, **test})
    if tests:
        pd.DataFrame(tests).to_csv(RESULTS_DIR / "wilcoxon.csv", index=False)
    plot(summaries)
    print(f"\n요약 파일을 {RESULTS_DIR.name} 폴더에 저장했습니다.")


if __name__ == "__main__":
    main()
