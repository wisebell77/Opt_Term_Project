import pytest

gurobipy = pytest.importorskip("gurobipy")  # Gurobi가 설치되지 않은 환경에서는 이 파일의 테스트를 건너뛴다
try:
    gurobipy.Model().dispose()
except gurobipy.GurobiError as error:  # 라이선스가 없거나 버전이 맞지 않는 경우
    pytest.skip(f"Gurobi를 사용할 수 없음: {error}", allow_module_level=True)

from src.instance import list_instances, load_instance  # noqa: E402
from src.milp import solve_milp  # noqa: E402
from src.schedule import validate  # noqa: E402
from tests.helpers import brute_force_optimum, hard_instances, tiny_instance  # noqa: E402


def test_milp_solves_the_hand_example():
    result = solve_milp(tiny_instance())
    assert (result["objective"], result["optimal"]) == (2, True)


def test_milp_matches_exhaustive_search_on_six_job_instances():
    instances = hard_instances()[:3] + [load_instance(p) for p in list_instances("small")[5:240:60]]
    for inst in instances:
        result = solve_milp(inst)
        assert result["optimal"], inst.name
        assert result["objective"] == brute_force_optimum(inst), inst.name


def test_milp_schedule_evaluates_to_the_reported_objective():
    for inst in hard_instances()[:3]:
        result = solve_milp(inst)
        assert validate(inst, result["schedule"]) == [], inst.name
        assert result["schedule"].total == result["objective"], inst.name


def test_largest_small_instance_fits_the_solver_license():
    inst = load_instance(list_instances("small")[-1])  # n = 12, m = 5
    assert solve_milp(inst)["optimal"]
