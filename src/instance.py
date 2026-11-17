"""인스턴스 자료 구조와 벤치마크 파일 파서.

모든 경로는 이 파일의 위치를 기준으로 계산하므로, codes 폴더를 어디에 두어도 동작한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

CODES_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = CODES_DIR / "data"
RESULTS_DIR = CODES_DIR / "results"


@dataclass
class Instance:
    """Rm | Mj, sijk | ΣTj 문제의 인스턴스. 작업과 기계의 번호는 0부터 시작한다."""

    name: str
    n: int  # 작업 수
    m: int  # 기계 수
    p: list  # p[i][j]: 기계 i에서 작업 j의 가공시간
    s: list  # s[i][j][k]: 기계 i에서 작업 j 바로 다음에 작업 k를 처리할 때의 준비시간
    d: list  # d[j]: 작업 j의 납기
    ok: list  # ok[i][j]: 기계 i에서 작업 j를 처리할 수 있으면 True
    elig: list = field(init=False)  # elig[j]: 작업 j의 적격 기계 목록
    jobs_of: list = field(init=False)  # jobs_of[i]: 기계 i에서 처리할 수 있는 작업 목록

    def __post_init__(self):
        self.elig = [[i for i in range(self.m) if self.ok[i][j]] for j in range(self.n)]
        self.jobs_of = [[j for j in range(self.n) if self.ok[i][j]] for i in range(self.m)]


def load_instance(path) -> Instance:
    """벤치마크 텍스트 파일 하나를 읽는다."""
    path = Path(path)
    # 줄바꿈이 CRLF이고 행 끝에 공백이 있으므로, 공백으로 분리한 뒤 빈 줄을 버린다.
    rows = [line.split() for line in path.read_text().splitlines()]
    rows = [r for r in rows if r]

    def numbers(start, count):
        return [[int(x) for x in r] for r in rows[start : start + count]]

    n, m = int(rows[1][0]), int(rows[1][1])
    pos = 3  # "Problem Size", 크기, "Processing Times" 다음 줄
    by_job = numbers(pos, n)  # n행 m열
    p = [[by_job[j][i] for j in range(n)] for i in range(m)]
    pos += n + 1  # "Setup Times"
    s = []
    for _ in range(m):
        pos += 1  # "M1", "M2", ...
        s.append(numbers(pos, n))  # 행은 선행 작업, 열은 후속 작업
        pos += n
    pos += 1  # "Eligibility"
    flags = numbers(pos, n)
    ok = [[flags[j][i] == 1 for j in range(n)] for i in range(m)]
    pos += n + 1  # "Due Dates"
    d = [r[0] for r in numbers(pos, n)]
    return Instance(path.stem, n, m, p, s, d, ok)


def parse_name(name: str) -> dict:
    """파일명에서 실험 요인을 꺼낸다. 예: I_6_2_49_50_T02_R02_1"""
    _, n, m, setup, p, tau, r, idx = name.split("_")
    return {
        "n": int(n),
        "m": int(m),
        "setup": int(setup),
        "p": int(p),
        "tau": int(tau[1:]) / 10,
        "R": int(r[1:]) / 10,
        "idx": int(idx),
    }


def list_instances(size: str) -> list:
    """data/<size> 폴더의 인스턴스 파일 경로를 요인 순서대로 정렬하여 돌려준다. size는 "small" 또는 "medium"이다."""
    paths = (DATA_DIR / size).glob("I_*.txt")
    return sorted(paths, key=lambda path: tuple(parse_name(path.stem).values()))
