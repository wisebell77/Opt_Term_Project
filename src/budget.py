"""실행 예산(종료 조건)과 알고리즘 실행 결과.

시간 제한 모드는 본 실험에 사용하고, 반복 횟수 모드는 같은 시드에서 같은 결과가 나와야 하는
단위 테스트와 수렴 곡선 기록에 사용한다. 반복의 단위는 CSA에서는 세대, SA에서는 이웃 해 평가이다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter


def time_limit_seconds(inst, scale=1.0, t=30):
    """논문의 시간 제한 n·m·t/2 밀리초에 속도 보정 계수 scale을 곱한 값(초)."""
    return scale * inst.n * inst.m * t / 2 / 1000


class Budget:
    def __init__(self, time_limit=None, max_iters=None):
        if (time_limit is None) == (max_iters is None):
            raise ValueError("time_limit과 max_iters 중 정확히 하나를 지정해야 한다")
        self.time_limit = time_limit
        self.max_iters = max_iters
        self.iters = 0
        self.started = perf_counter()

    def start(self):
        self.iters = 0
        self.started = perf_counter()

    def tick(self, count=1):
        self.iters += count

    def elapsed(self):
        return perf_counter() - self.started

    def progress(self):
        """사용한 예산의 비율(0 이상 1 이하)."""
        if self.max_iters is not None:
            return min(self.iters / self.max_iters, 1.0)
        return min(self.elapsed() / self.time_limit, 1.0)

    def done(self):
        return self.progress() >= 1.0


@dataclass
class Result:
    schedule: object  # 탐색 중 발견한 최선해(Schedule)
    objective: int  # 총 순수지연시간
    elapsed: float  # 실행 시간(초)
    iterations: int  # CSA는 세대 수, SA는 평가 횟수
    info: dict = field(default_factory=dict)  # 알고리즘별 부가 기록
