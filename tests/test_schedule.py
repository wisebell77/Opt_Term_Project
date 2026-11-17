from src.schedule import Schedule, job_tardiness, machine_cost, validate
from tests.helpers import tiny_instance


def test_machine_cost_matches_hand_calculation():
    inst = tiny_instance()
    # 기계 0: 작업 0(C=3, T=0) -> 작업 2(C=3+3+2=8, T=2)
    assert machine_cost(inst, 0, [0, 2]) == (2, 11)
    # 기계 1: 작업 3(C=3, T=0) -> 작업 1(C=3+3+2=8, T=0)
    assert machine_cost(inst, 1, [3, 1]) == (0, 11)
    # 기계 0: 작업 2(C=2) -> 작업 0(C=2+2+3=7, T=3) -> 작업 1(C=7+2+5=14, T=5)
    assert machine_cost(inst, 0, [2, 0, 1]) == (8, 23)
    assert machine_cost(inst, 0, []) == (0, 0)


def test_first_job_has_no_setup_time():
    inst = tiny_instance()
    assert machine_cost(inst, 1, [1]) == (0, 2)  # 완료시간은 가공시간과 같다


def test_job_tardiness_lists_each_position():
    inst = tiny_instance()
    assert job_tardiness(inst, 0, [2, 0, 1]) == [0, 3, 5]


def test_schedule_tracks_total_when_a_machine_changes():
    inst = tiny_instance()
    sched = Schedule.from_seqs(inst, [[0, 2], [3, 1]])
    assert (sched.total, sched.tard, sched.csum) == (2, [2, 0], [11, 11])
    sched.set_machine(inst, 0, [2, 0])
    assert (sched.total, sched.tard) == (3, [3, 0])
    clone = sched.copy()
    clone.set_machine(inst, 0, [0, 2])
    assert (sched.total, clone.total) == (3, 2)  # 복사본을 바꿔도 원본은 그대로이다


def test_validate_accepts_a_correct_schedule():
    inst = tiny_instance()
    assert validate(inst, Schedule.from_seqs(inst, [[0, 2], [3, 1]])) == []


def test_validate_reports_missing_duplicate_and_ineligible_jobs():
    inst = tiny_instance()
    assert validate(inst, Schedule.from_seqs(inst, [[0, 2], [3]])) != []  # 작업 1 누락
    assert validate(inst, Schedule.from_seqs(inst, [[0, 2, 1], [3, 1]])) != []  # 작업 1 중복
    assert validate(inst, Schedule.from_seqs(inst, [[0], [3, 1, 2]])) != []  # 작업 2는 기계 1에 비적격


def test_validate_reports_stale_cached_cost():
    inst = tiny_instance()
    sched = Schedule.from_seqs(inst, [[0, 2], [3, 1]])
    sched.seqs[0].reverse()  # 비용을 갱신하지 않고 순서만 바꾼 경우
    assert validate(inst, sched) != []
