import pandas as pd
import pytest

from experiments import analyze
from experiments.analyze import instance_table, method_summary
from experiments.run import DEFAULT_METHODS, METHODS, make_seed, run_instance
from src.instance import DATA_DIR
from tests.helpers import HARD


def test_seed_is_reproducible_and_distinct_per_repetition():
    assert make_seed("I_6_2_49_50_T04_R02_1", "csa_f", 0) == make_seed("I_6_2_49_50_T04_R02_1", "csa_f", 0)
    assert make_seed("I_6_2_49_50_T04_R02_1", "csa_f", 0) != make_seed("I_6_2_49_50_T04_R02_1", "csa_f", 1)
    assert make_seed("I_6_2_49_50_T04_R02_1", "csa_f", 0) != make_seed("I_6_2_49_50_T04_R02_1", "csa_t", 0)


def test_run_instance_produces_one_row_per_method_and_repetition():
    path = DATA_DIR / (HARD[0] + ".txt")
    rows = run_instance((str(path), DEFAULT_METHODS, 2, 0.2, "test", set(), None))
    assert len(rows) == 1 + 5 * 2  # H5는 한 번, 나머지 다섯 방법은 2회씩
    by_method = {}
    for row in rows:
        by_method.setdefault(row["method"], []).append(row)
    assert set(by_method) == set(DEFAULT_METHODS)
    assert set(DEFAULT_METHODS) < set(METHODS)  # 제한 목록을 개수로 읽는 변형은 기본 목록에 넣지 않는다
    first = by_method["csa_t"][0]
    assert (first["instance"], first["n"], first["m"], first["tau"]) == ("I_6_2_49_50_T04_R02_1", 6, 2, 0.4)
    assert first["time_limit"] == pytest.approx(0.2 * 6 * 2 * 30 / 2 / 1000)
    assert all(row["objective"] <= by_method["h5"][0]["objective"] for row in by_method["csa_t"] + by_method["sa_geo"])


def test_run_instance_skips_finished_work():
    path = DATA_DIR / (HARD[0] + ".txt")
    done = {("I_6_2_49_50_T04_R02_1", "h5", 0), ("I_6_2_49_50_T04_R02_1", "csa_f", 0)}
    rows = run_instance((str(path), ["h5", "csa_f"], 2, 0.2, "test", done, None))
    assert [(row["method"], row["rep"]) for row in rows] == [("csa_f", 1)]


def test_run_instance_rejects_results_below_the_known_optimum():
    path = DATA_DIR / (HARD[0] + ".txt")
    with pytest.raises(AssertionError):
        run_instance((str(path), ["h5"], 1, 0.2, "test", set(), 10**9))


def runs_frame():
    rows = [
        # 인스턴스 A: 기준값 10, 인스턴스 B: 기준값 0
        ("A", "x", 0, 10), ("A", "x", 1, 12), ("B", "x", 0, 0), ("B", "x", 1, 0),
        ("A", "y", 0, 20), ("A", "y", 1, 20), ("B", "y", 0, 3), ("B", "y", 1, 5),
    ]
    return pd.DataFrame(rows, columns=["instance", "method", "rep", "objective"])


def test_instance_table_computes_rpd_rdi_and_hit_rate():
    table = instance_table(runs_frame(), pd.Series({"A": 10, "B": 0})).set_index(["instance", "method"])
    assert table.loc[("A", "x"), "mean_obj"] == 11
    assert table.loc[("A", "x"), "rpd"] == pytest.approx(10.0)
    assert table.loc[("A", "y"), "rpd"] == pytest.approx(100.0)
    assert pd.isna(table.loc[("B", "x"), "rpd"])  # 기준값이 0이면 RPD를 정의하지 않는다
    assert table.loc[("B", "y"), "gap"] == 4
    assert (table.loc[("A", "x"), "rdi"], table.loc[("A", "y"), "rdi"]) == (0, 100)
    assert (table.loc[("B", "x"), "rdi"], table.loc[("B", "y"), "rdi"]) == (0, 100)
    assert (table.loc[("A", "x"), "hit"], table.loc[("B", "x"), "hit"], table.loc[("B", "y"), "hit"]) == (0.5, 1.0, 0.0)


def test_rdi_is_zero_when_every_method_ties():
    runs = pd.DataFrame([("A", "x", 0, 7), ("A", "y", 0, 7)], columns=["instance", "method", "rep", "objective"])
    assert list(instance_table(runs, pd.Series({"A": 7}))["rdi"]) == [0, 0]


def test_method_summary_separates_zero_and_positive_reference_instances():
    summary = method_summary(instance_table(runs_frame(), pd.Series({"A": 10, "B": 0}))).set_index("method")
    assert summary.loc["x", "rpd_mean"] == pytest.approx(10.0)  # 기준값이 양수인 인스턴스만 평균한다
    assert summary.loc["y", "gap0_mean"] == 4  # 기준값이 0인 인스턴스의 절대 차이
    assert summary.loc["y", "rdi_mean"] == 100
    assert summary.loc["x", "hit_rate"] == 0.75
    assert (summary.loc["x", "instances"], summary.loc["x", "ref_zero"]) == (2, 1)


def test_analyze_size_works_when_no_milp_result_exists(tmp_path, monkeypatch):
    # 중규모처럼 MILP 결과가 없는 경우에는 실행한 방법들의 최선값을 기준값으로 사용한다
    monkeypatch.setattr(analyze, "RESULTS_DIR", tmp_path)
    factors = {"size": "medium", "n": 15, "m": 2, "setup": 49, "p": 50, "tau": 0.4, "R": 0.2, "idx": 1, "elapsed": 0.1}
    rows = [("A", "csa_t", 0, 30), ("A", "sa_geo", 0, 20), ("B", "csa_t", 0, 0), ("B", "sa_geo", 0, 0)]
    runs = pd.DataFrame([{"instance": i, "method": m, "rep": r, "objective": o, **factors} for i, m, r, o in rows])
    summary, test = analyze.analyze_size(runs, "medium", ["csa_t", "sa_geo"])
    assert summary.set_index("method").loc["csa_t", "rpd_mean"] == pytest.approx(50.0)
    assert (test["first_better"], test["ties"], test["second_better"]) == (0, 1, 1)
    assert (tmp_path / "summary_medium.csv").exists()
