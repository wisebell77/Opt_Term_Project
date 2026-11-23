"""수렴 곡선: 인스턴스 하나에서 SA_t의 냉각 방식 3종을 같은 평가 횟수로 실행하여 최선값의 변화를 그린다.

사용 예 (codes 폴더에서 실행):
    python -m experiments.convergence --instance medium/I_15_2_124_100_T04_R02_1 --evals 200000

평가 횟수 기준으로 실행하므로 같은 시드에서는 어느 컴퓨터에서나 같은 결과가 나온다.
출발해인 H5에는 팀의 동점 처리 기준(random)을 적용하며, --tie로 바꿀 수 있다.
"""
from __future__ import annotations

import argparse
import random

from src import tiebreak
from src.budget import Budget
from src.instance import DATA_DIR, RESULTS_DIR, load_instance
from src.sa import sa_t


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--instance", required=True, help="data 폴더 기준 경로(확장자 제외). 예: small/I_6_2_49_50_T04_R02_1")
    parser.add_argument("--evals", type=int, default=200000, help="이웃 해 평가 횟수")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--tie", default=tiebreak.BASELINE, choices=tiebreak.MODES, help="H5 출발해에 적용할 동점 처리 기준")
    args = parser.parse_args()

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    inst = load_instance(DATA_DIR / f"{args.instance}.txt")
    fig, axis = plt.subplots(figsize=(6, 3.6))
    for cooling, style in (("geo", "-"), ("log", "--"), ("exp", ":")):
        rng = random.Random(args.seed)
        with tiebreak.policy(args.tie, rng):
            result = sa_t(inst, rng, Budget(max_iters=args.evals), cooling)
        trace = result.info.get("trace", [(0, result.objective)]) + [(result.iterations, result.objective)]
        axis.step([e for e, _ in trace], [v for _, v in trace], style, where="post", color="black", label=cooling)
        print(f"{cooling}: 최선값 {result.objective}, 종료 온도 {result.info.get('t_end', float('nan')):.3f}, "
              f"목표 종료 온도 {result.info.get('tf', float('nan')):.3f}")
    axis.set_xlabel("Evaluations")
    axis.set_ylabel("Best total tardiness")
    axis.set_title(inst.name)
    axis.legend(title="cooling")
    fig.tight_layout()
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"convergence_{inst.name}.png"
    fig.savefig(out, dpi=200)
    print(f"그림을 {out.relative_to(RESULTS_DIR.parent)}에 저장했습니다.")


if __name__ == "__main__":
    main()
