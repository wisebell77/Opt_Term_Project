"""삽입 연산 BestPosition과 BestPosition_Total.

동점 처리(논문 5.2절): 기계의 지연이 삽입 전에도 0이고 삽입 후에도 0이면 Σ(C_j - d_j)가 최소인 위치
(= 완료시간 합이 최소인 위치)를 고른다. 그 밖의 동점은 논문이 정하지 않았으므로 위치가 앞선 쪽,
기계 사이의 동점은 기계 번호가 작은 쪽을 고른다. 논문이 정하지 않은 동점은 tiebreak 모듈의 기준으로
바꿀 수 있으며, 위의 설명은 기본 기준(first)의 동작이다.
"""
from __future__ import annotations

from . import tiebreak


def profile(inst, i, seq):
    """기계 i의 현재 순서에 대한 누적 정보. 같은 기계에 여러 작업의 삽입을 시험할 때 한 번만 계산한다."""
    p, s, d = inst.p[i], inst.s[i], inst.d
    comp, due, pref_t, pref_c = [], [], [0], [0]
    t, prev = 0, -1
    for j in seq:
        t += p[j] if prev < 0 else s[prev][j] + p[j]
        comp.append(t)
        due.append(d[j])
        pref_t.append(pref_t[-1] + (t - d[j] if t > d[j] else 0))
        pref_c.append(pref_c[-1] + t)
        prev = j
    return comp, due, pref_t, pref_c


def best_insert(inst, i, seq, prof, j):
    """작업 j를 기계 i에 삽입할 때의 최선 (삽입 후 지연 합, 삽입 후 완료시간 합, 위치)."""
    comp, due, pref_t, pref_c = prof
    p, s = inst.p[i], inst.s[i]
    pj, dj, s_from_j = p[j], inst.d[j], s[j]
    size = len(seq)
    total_c = pref_c[size]
    base_t = pref_t[size]  # 삽입 전 기계의 지연 합
    # 동점 처리 기준. 이 함수는 가장 자주 호출되므로 tiebreak.rank를 부르지 않고 같은 규칙을 직접 계산한다
    by_csum = tiebreak.mode == "csum"
    sign = -1 if tiebreak.mode == "last" else 1
    draw = tiebreak.rng.random if tiebreak.mode == "random" else None
    best_t = best_c = best_pos = best_k = best_r = -1
    for pos in range(size + 1):
        cj = comp[pos - 1] + s[seq[pos - 1]][j] + pj if pos else pj
        t = pref_t[pos] + (cj - dj if cj > dj else 0)
        if best_pos >= 0 and t > best_t:
            continue
        c = pref_c[pos] + cj
        if pos < size:
            # 뒤에 오는 작업들은 완료시간이 모두 shift만큼 밀린다
            nxt = seq[pos]
            shift = cj + s_from_j[nxt] + p[nxt] - comp[pos]
            c += total_c - pref_c[pos] + shift * (size - pos)
            for r in range(pos, size):
                late = comp[r] + shift - due[r]
                if late > 0:
                    t += late
            if best_pos >= 0 and t > best_t:
                continue
        # 지연이 같은 위치 사이의 비교: 논문의 규칙이 적용되는 경우(와 기준 csum)에는 완료시간 합 k, 이어서 기준의 순서 r
        k = c if by_csum or t == base_t == 0 else 0
        r = draw() if draw else sign * pos
        if best_pos < 0 or t < best_t or k < best_k or (k == best_k and r < best_r):
            best_t, best_c, best_pos, best_k, best_r = t, c, pos, k, r
    return best_t, best_c, best_pos


def best_position(inst, i, seq, j):
    """BestPosition(j, i): 기계 i의 지연 합을 가장 작게 만드는 위치를 찾는다."""
    return best_insert(inst, i, seq, profile(inst, i, seq), j)


def best_position_total(inst, sched, j):
    """BestPosition_Total(j): 모든 적격 기계의 모든 위치 중 총 지연을 가장 작게 만드는 (기계, 위치)."""
    best = None
    for i in inst.elig[j]:
        tard, csum, pos = best_position(inst, i, sched.seqs[i], j)
        key = (tard - sched.tard[i], tiebreak.csum(csum - sched.csum[i]), *tiebreak.rank(i), i, pos)
        if best is None or key < best:
            best = key
    return best[-2], best[-1]


def insert(inst, sched, i, pos, j):
    """작업 j를 기계 i의 pos 위치에 넣고 비용을 갱신한다."""
    seq = sched.seqs[i]
    sched.set_machine(inst, i, seq[:pos] + [j] + seq[pos:])
