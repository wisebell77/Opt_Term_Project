"""동점 처리 기준: 총 지연(또는 그 변화량)이 같은 후보가 여럿일 때 무엇을 고를지 정한다.

논문이 정한 규칙(BestPosition에서 삽입 전후 기계의 지연이 모두 0이면 완료시간 합이 작은 위치)은
모든 기준에서 유지된다. 논문이 정하지 않은 나머지 동점만 기준에 따라 달라진다.

- first:  살펴보는 순서에서 앞선 후보(작업 번호, 기계 번호, 위치가 작은 쪽). 기본값이다.
- last:   뒤쪽 후보(번호와 위치가 큰 쪽).
- csum:   완료시간 합이 작은 후보, 그래도 같으면 앞선 후보(main 브랜치가 쓰던 규칙).
- random: 동점인 후보 가운데 하나를 같은 확률로 고른다.

기준이 적용되는 지점은 BestPosition, BestPosition_Total, GRASP(작업을 넣을 기계와 제한 목록의 순서),
내부 교환, 외부 삽입, 외부 교환이다. 기준은 `with policy("last"):`처럼 구간을 정해 바꾼다.
"""
from __future__ import annotations

from contextlib import contextmanager

MODES = ("first", "last", "csum", "random")

mode = "first"  # 현재 기준
rng = None  # 기준 random이 쓰는 난수 생성기


@contextmanager
def policy(new_mode, new_rng=None):
    """구간 안에서 동점 처리 기준을 new_mode로 바꾼다. random은 난수 생성기(random.Random)가 필요하다."""
    global mode, rng
    if new_mode not in MODES:
        raise ValueError(f"알 수 없는 동점 처리 기준: {new_mode}")
    if new_mode == "random" and new_rng is None:
        raise ValueError("기준 random에는 난수 생성기가 필요하다")
    previous = mode, rng
    mode, rng = new_mode, new_rng
    try:
        yield
    finally:
        mode, rng = previous


def csum(value):
    """동점 비교에 쓸 완료시간 합. 기준 csum에서만 값을 그대로 쓰고, 나머지 기준에서는 비교하지 않는다(0)."""
    return value if mode == "csum" else 0


def rank(*index):
    """동점인 후보 사이의 순서를 정하는 키(작은 쪽을 고른다). index는 후보의 번호나 위치이다."""
    if mode == "last":
        return tuple(-value for value in index)
    if mode == "random":
        return (rng.random(),)
    return index
