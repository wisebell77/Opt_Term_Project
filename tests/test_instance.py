from src.instance import DATA_DIR, list_instances, load_instance, parse_name


def test_load_instance_reads_every_section():
    inst = load_instance(DATA_DIR / "small" / "I_6_2_49_50_T02_R02_1.txt")
    assert (inst.n, inst.m) == (6, 2)
    assert inst.p[0] == [64, 21, 77, 48, 3, 7]  # 기계 1의 가공시간
    assert inst.p[1] == [61, 94, 26, 54, 39, 83]
    assert inst.s[0][0] == [0, 17, 45, 19, 49, 22]  # 기계 1에서 작업 1 다음에 오는 준비시간
    assert inst.s[1][5] == [48, 19, 3, 4, 9, 0]
    assert inst.d == [289, 288, 243, 230, 270, 271]
    assert inst.elig == [[0, 1], [0], [0], [1], [1], [0]]
    assert inst.jobs_of == [[0, 1, 2, 5], [0, 3, 4]]


def test_parse_name_extracts_factors():
    f = parse_name("I_40_8_124_100_T04_R02_10")
    assert f == {"n": 40, "m": 8, "setup": 124, "p": 100, "tau": 0.4, "R": 0.2, "idx": 10}


def test_list_instances_counts_and_order():
    small, medium = list_instances("small"), list_instances("medium")
    assert (len(small), len(medium)) == (3840, 5760)
    assert small[0].name == "I_6_2_49_50_T02_R02_1.txt"
    assert small[1].name == "I_6_2_49_50_T02_R02_2.txt"  # 번호는 숫자 순서로 정렬한다
    assert small[9].name == "I_6_2_49_50_T02_R02_10.txt"


def test_every_instance_is_well_formed():
    for path in list_instances("small") + list_instances("medium"):
        inst = load_instance(path)
        f = parse_name(inst.name)
        assert (inst.n, inst.m) == (f["n"], f["m"]), path.name
        assert all(inst.elig), path.name  # 모든 작업에 적격 기계가 있다
        assert all(inst.jobs_of), path.name  # 모든 기계에 처리할 수 있는 작업이 있다
        assert all(1 <= x <= 99 for row in inst.p for x in row), path.name
        assert all(0 <= x <= f["setup"] for mat in inst.s for row in mat for x in row), path.name
