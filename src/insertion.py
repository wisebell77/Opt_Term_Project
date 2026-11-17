"""삽입 연산 BestPosition과 BestPosition_Total.

동점 처리: 지연 합이 같으면 완료시간 합이 작은 쪽, 그래도 같으면 기계 번호와 위치가 작은 쪽을 고른다.
"""
from __future__ import annotations


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
    best_t = best_c = best_pos = -1
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
        if best_pos < 0 or t < best_t or (t == best_t and c < best_c):
            best_t, best_c, best_pos = t, c, pos
    return best_t, best_c, best_pos


def best_position(inst, i, seq, j):
    """BestPosition(j, i): 기계 i의 지연 합을 가장 작게 만드는 위치를 찾는다."""
    return best_insert(inst, i, seq, profile(inst, i, seq), j)


def best_position_total(inst, sched, j):
    """BestPosition_Total(j): 모든 적격 기계의 모든 위치 중 총 지연을 가장 작게 만드는 (기계, 위치)."""
    best = None
    for i in inst.elig[j]:
        tard, csum, pos = best_position(inst, i, sched.seqs[i], j)
        key = (tard - sched.tard[i], csum - sched.csum[i], i, pos)
        if best is None or key < best:
            best = key
    return best[2], best[3]


def insert(inst, sched, i, pos, j):
    """작업 j를 기계 i의 pos 위치에 넣고 비용을 갱신한다."""
    seq = sched.seqs[i]
    sched.set_machine(inst, i, seq[:pos] + [j] + seq[pos:])
