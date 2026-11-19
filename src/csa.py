"""클론 선택 알고리즘 CSA_f, CSA_t.

대상 논문(Perez-Gonzalez et al., 2019)의 6절을 문면 그대로 따른다(paper-faithful 브랜치).
- GRASP 제한 목록의 크기 k = 5는 작업 5개이다(rcl_percent=True이면 미배정 작업의 5%로 읽는다).
- 수용체 편집은 논문의 외부 삽입/외부 교환 연산자를 쓴다(개선이 있을 때만 이동). pmut의 확률로 외부 교환을,
  그렇지 않으면 외부 삽입을 쓰며, 논문의 값 PMUT = 0이므로 외부 삽입만 쓰인다.
  receptor_random=True이면 Diana et al.(2015)처럼 수락 검사가 없는 무작위 이동을 쓴다.
- 재선택은 중복 제거나 무작위 섞기 없이 목적함수 오름차순(안정 정렬)으로 진행한다.
- 우선도는 개선된 해에서 100이 되고, 개선되지 않은 세대마다 D_PRIOR만큼 낮아진다(논문은 세부를 적지 않음).
- 시간 제한은 세대가 끝날 때마다 확인한다. 한 세대는 도중에 끊기지 않는다(논문의 Algorithm 5).
논문에 없는 본 프로젝트의 규칙은 src/README.md에 정리되어 있다.
"""
from __future__ import annotations

from .budget import Result
from .h5 import h5
from .insertion import best_insert, profile
from .schedule import Schedule, machine_cost

# 논문의 파라미터 값
MU = 20  # 기억 집합의 크기
K_RCL = 5  # GRASP 제한 목록의 크기(기본 해석은 작업 5개)
NC = 60  # 세대당 클론 수
D_PRIOR = 5  # 우선도 감소량
MUTMAX = 2  # 다양화 변이의 최대 횟수
PMUT = 0.0  # 다양화 변이에서 외부 교환을 선택할 확률
X = 4  # 재선택 후보 목록의 크기


# ---------- 초기 해 생성 ----------

def rcl_size(remaining, percent=False):
    """GRASP 제한 목록의 크기. K_RCL을 미배정 작업에 대한 비율(%)로 읽거나(Diana et al., 2015), 작업의 개수로 읽는다(대상 논문의 문면)."""
    if percent:
        return max(1, -(-K_RCL * remaining // 100))
    return min(K_RCL, remaining)


def grasp(inst, rng, percent=False):
    """미배정 작업 중 삽입 후 총 지연이 작은 작업들로 제한 목록을 만들고, 하나를 무작위로 골라 최선 위치에 넣는 과정을 반복한다."""
    sched = Schedule.empty(inst)
    empty = profile(inst, 0, [])
    # best[j][i] = 작업 j를 기계 i에 넣을 때의 (지연 증가량, 완료시간 합 증가량, 위치)
    best = [{i: best_insert(inst, i, [], empty, j) for i in inst.elig[j]} for j in range(inst.n)]
    rest = list(range(inst.n))
    while rest:
        # 제한 목록은 삽입 후 총 지연이 작은 순서이며, 동점은 논문이 정하지 않았으므로 작업 번호 순으로 둔다
        options = sorted((d, j, i, pos) for j in rest for d, i, pos in [min((best[j][i][0], i, best[j][i][2]) for i in inst.elig[j])])
        _, j, i, pos = rng.choice(options[: rcl_size(len(rest), percent)])
        seq = sched.seqs[i]
        sched.set_machine(inst, i, seq[:pos] + [j] + seq[pos:])
        rest.remove(j)
        # 순서가 바뀐 기계 i에 대한 삽입 비용만 다시 계산한다
        seq, prof = sched.seqs[i], profile(inst, i, sched.seqs[i])
        for other in rest:
            if inst.ok[i][other]:
                tard, csum, at = best_insert(inst, i, seq, prof, other)
                best[other][i] = (tard - sched.tard[i], csum - sched.csum[i], at)
    return sched


# ---------- 이웃 연산자 (i*는 지연 합이 가장 큰 기계) ----------

def worst_machine(sched):
    return max(range(len(sched.tard)), key=sched.tard.__getitem__)


def int_swap(inst, sched, rng=None):
    """내부 교환: i* 안에서 두 작업을 맞바꾸는 모든 경우 중 가장 좋은 경우를 적용한다."""
    i = worst_machine(sched)
    if sched.tard[i] == 0:
        return False
    seq = sched.seqs[i][:]
    best = (sched.tard[i],)
    for a in range(len(seq) - 1):
        for b in range(a + 1, len(seq)):
            seq[a], seq[b] = seq[b], seq[a]
            key = (machine_cost(inst, i, seq)[0], a, b)  # 지연이 같으면 먼저 찾은 쌍(논문에 동점 규정 없음)
            if key[0] < sched.tard[i] and key < best:
                best = key
            seq[a], seq[b] = seq[b], seq[a]
    if len(best) == 1:
        return False
    a, b = best[1], best[2]
    seq[a], seq[b] = seq[b], seq[a]
    sched.set_machine(inst, i, seq)
    return True


def ext_insert(inst, sched, rng):
    """외부 삽입: i*의 작업 하나를 무작위로 고른 다른 기계로 옮긴다. 개선이 없으면 다른 기계를 시도한다."""
    i = worst_machine(sched)
    if sched.tard[i] == 0:
        return False
    seq_i = sched.seqs[i]
    removed = [machine_cost(inst, i, seq_i[:a] + seq_i[a + 1 :]) for a in range(len(seq_i))]
    others = [w for w in range(inst.m) if w != i]
    rng.shuffle(others)
    for w in others:
        seq_w = sched.seqs[w]
        prof = profile(inst, w, seq_w)
        best = None
        for a, j in enumerate(seq_i):
            if not inst.ok[w][j]:
                continue
            tard_w, csum_w, pos = best_insert(inst, w, seq_w, prof, j)
            key = (
                removed[a][0] + tard_w - sched.tard[i] - sched.tard[w],
                a,
                pos,
            )
            if best is None or key < best:
                best = key
        if best is not None and best[0] < 0:
            _, a, pos = best
            j = seq_i[a]
            sched.set_machine(inst, i, seq_i[:a] + seq_i[a + 1 :], removed[a])
            sched.set_machine(inst, w, seq_w[:pos] + [j] + seq_w[pos:])
            return True
    return False


def ext_swap(inst, sched, rng):
    """외부 교환: i*의 작업 하나와 무작위로 고른 다른 기계의 작업 하나를 맞바꾼다."""
    i = worst_machine(sched)
    if sched.tard[i] == 0:
        return False
    others = [w for w in range(inst.m) if w != i]
    rng.shuffle(others)
    ok_i, seq_i = inst.ok[i], sched.seqs[i][:]
    for w in others:
        ok_w, seq_w = inst.ok[w], sched.seqs[w][:]
        base_t = sched.tard[i] + sched.tard[w]
        best = None
        for a, ja in enumerate(seq_i):
            if not ok_w[ja]:
                continue
            for b, jb in enumerate(seq_w):
                if not ok_i[jb]:
                    continue
                seq_i[a], seq_w[b] = jb, ja
                cost_i, cost_w = machine_cost(inst, i, seq_i), machine_cost(inst, w, seq_w)
                seq_i[a], seq_w[b] = ja, jb
                key = (cost_i[0] + cost_w[0] - base_t, a, b)
                if best is None or key < best:
                    best = key
        if best is not None and best[0] < 0:
            _, a, b = best
            seq_i[a], seq_w[b] = seq_w[b], seq_i[a]
            sched.set_machine(inst, i, seq_i)
            sched.set_machine(inst, w, seq_w)
            return True
    return False


def vnd(inst, sched, rng):
    """집중화 변이: 내부 교환, 외부 삽입, 외부 교환 순서의 VND. 개선되면 첫 이웃으로 돌아간다."""
    operators = (int_swap, ext_insert, ext_swap)
    k = 0
    while k < len(operators):
        k = 0 if operators[k](inst, sched, rng) else k + 1


def random_ext_insert(inst, sched, rng):
    """무작위 외부 삽입: 임의의 작업을 다른 적격 기계의 임의 위치로 옮긴다. 수락 검사를 하지 않는다."""
    movable = [j for j in range(inst.n) if len(inst.elig[j]) > 1]
    if not movable:
        return False
    j = rng.choice(movable)
    i = next(i for i, seq in enumerate(sched.seqs) if j in seq)
    w = rng.choice([x for x in inst.elig[j] if x != i])
    seq_i, seq_w = sched.seqs[i], sched.seqs[w]
    a, pos = seq_i.index(j), rng.randrange(len(seq_w) + 1)
    sched.set_machine(inst, i, seq_i[:a] + seq_i[a + 1 :])
    sched.set_machine(inst, w, seq_w[:pos] + [j] + seq_w[pos:])
    return True


def random_ext_swap(inst, sched, rng):
    """무작위 외부 교환: 서로 다른 기계에 있고 상대 기계에 적격인 두 작업을 맞바꾼다. 수락 검사를 하지 않는다."""
    where = {j: i for i, seq in enumerate(sched.seqs) for j in seq}
    pairs = [
        (j, k)
        for j in range(inst.n)
        for k in range(j + 1, inst.n)
        if where[j] != where[k] and inst.ok[where[k]][j] and inst.ok[where[j]][k]
    ]
    if not pairs:
        return False
    j, k = rng.choice(pairs)
    i, w = where[j], where[k]
    seq_i, seq_w = sched.seqs[i][:], sched.seqs[w][:]
    seq_i[seq_i.index(j)], seq_w[seq_w.index(k)] = k, j
    sched.set_machine(inst, i, seq_i)
    sched.set_machine(inst, w, seq_w)
    return True


def receptor_editing(inst, sched, rng, random_moves=False):
    """다양화 변이: U[1, MUTMAX]회의 변이. 확률 PMUT로 외부 교환을, 그렇지 않으면 외부 삽입을 적용한다.

    기본(논문 6절)은 i*에 대한 외부 삽입/교환 연산자를 그대로 쓰며 개선이 없으면 이동하지 않는다.
    random_moves=True이면 Diana et al.(2015)처럼 수락 검사 없는 무작위 이동을 쓴다."""
    if random_moves:
        swap, insert = random_ext_swap, random_ext_insert
    else:
        swap, insert = ext_swap, ext_insert
    for _ in range(rng.randint(1, MUTMAX)):
        move = swap if rng.random() < PMUT else insert
        move(inst, sched, rng)


# ---------- 개체군 연산 ----------

class Cell:
    """기억 집합의 원소: 해와 우선도."""

    __slots__ = ("sched", "prio", "_pred")

    def __init__(self, sched, prio=100):
        self.sched = sched
        self.prio = prio
        self._pred = None

    def pred(self):
        """작업별 (기계, 직전 작업). 기계의 첫 작업은 직전 작업을 -1로 둔다."""
        if self._pred is None:
            pred = {}
            for i, seq in enumerate(self.sched.seqs):
                prev = -1
                for j in seq:
                    pred[j] = (i, prev)
                    prev = j
            self._pred = [pred[j] for j in sorted(pred)]
        return self._pred


def clone_priority(parent_prio, improved):
    """클론의 우선도: 부모보다 개선되었으면 100, 아니면 부모의 우선도에서 D_PRIOR만큼 낮춘 값(하한 0)."""
    return 100 if improved else max(0, parent_prio - D_PRIOR)


def distance(a, b):
    """두 해의 거리: 같은 기계에서 직전 작업이 서로 다른 작업의 수."""
    return sum(1 for x, y in zip(a.pred(), b.pred()) if x != y)


def fitness(cells):
    """적합도 F = (순위 점수의 비율 + 우선도의 비율) / 2."""
    size = len(cells)
    order = sorted(range(size), key=lambda a: cells[a].sched.total)
    rank = [0] * size
    for position, a in enumerate(order):
        rank[a] = position + 1
    rank_sum = sum(rank)
    score = [1 - r / rank_sum for r in rank]
    score_sum = sum(score)
    prio_sum = sum(cell.prio for cell in cells)
    return [
        ((score[a] / score_sum if score_sum else 1 / size) + (cells[a].prio / prio_sum if prio_sum else 1 / size)) / 2
        for a in range(size)
    ]


def reselect(pool, rng, size=MU, x=X):
    """목적함수가 좋은 해와, 이미 고른 해들에서 멀리 떨어진 해로 다음 기억 집합을 구성한다(논문 6절).

    pool을 목적함수 오름차순으로 안정 정렬한다(같은 해의 반복을 허용하며, 동점은 pool의 앞쪽이 먼저)."""
    pool = sorted(pool, key=lambda cell: cell.sched.total)
    chosen = [pool[0]]
    window = [(distance(cell, pool[0]), cell) for cell in pool[1 : 1 + x]]  # (고른 해들과의 최소 거리, 해)
    upcoming = 1 + x
    while len(chosen) < size and window:
        pick = max(range(len(window)), key=lambda a: window[a][0])
        picked = window.pop(pick)[1]
        chosen.append(picked)
        window = [(min(dist, distance(cell, picked)), cell) for dist, cell in window]
        if upcoming < len(pool):
            cell = pool[upcoming]
            window.append((min(distance(cell, other) for other in chosen), cell))
            upcoming += 1
    return chosen


# ---------- 알고리즘 본체 ----------

def csa(inst, rng, budget, use_h5, rcl_percent=False, receptor_random=False):
    budget.start()
    cells = [Cell(h5(inst))] if use_h5 else []
    while len(cells) < MU and not (cells and (budget.done() or cells[-1].sched.total == 0)):
        cells.append(Cell(grasp(inst, rng, rcl_percent)))
    best = min(cells, key=lambda cell: cell.sched.total).sched
    trace = [best.total]  # 세대별 최선값
    while best.total > 0 and not budget.done():
        parents = cells + rng.choices(cells, weights=fitness(cells), k=NC - len(cells))
        clones = []
        for parent in parents:  # 시간 제한은 세대마다 한 번 확인한다(논문의 Algorithm 5의 while 조건)
            clone = parent.sched.copy()
            receptor_editing(inst, clone, rng, receptor_random)
            vnd(inst, clone, rng)
            clones.append(Cell(clone, clone_priority(parent.prio, clone.total < parent.sched.total)))
            if clone.total < best.total:
                best = clone
                if best.total == 0:
                    break
        for cell in cells:
            cell.prio = max(0, cell.prio - D_PRIOR)
        cells = reselect(cells + clones, rng)
        budget.tick()
        trace.append(best.total)
    return Result(best.copy(), best.total, budget.elapsed(), budget.iters, {"trace": trace})


def csa_f(inst, rng, budget, rcl_percent=False, receptor_random=False):
    """초기 기억 집합을 GRASP만으로 생성한다."""
    return csa(inst, rng, budget, False, rcl_percent, receptor_random)


def csa_t(inst, rng, budget, rcl_percent=False, receptor_random=False):
    """초기 기억 집합에 H5의 해를 포함한다."""
    return csa(inst, rng, budget, True, rcl_percent, receptor_random)
