# results/first: 동점 처리 기준 first로 실행한 이전 결과

이 폴더에는 팀의 동점 처리 기준을 `random`으로 정하기 전에 실행한 결과가 들어 있습니다. 모두 기준 `first`(번호와 위치가 작은 쪽)로 실행한 것이며, 현재의 본 실험 결과(`results/raw_<크기>_full.csv`)와는 조건이 다릅니다. 기록으로 남겨 둔 것이므로 최종 비교에는 사용하지 않습니다.

## 파일

| 파일 | 내용 | 실행한 곳 |
|---|---|---|
| `raw_small_full.csv` | 소규모 3,840개에서 H5(1회), CSA_f, CSA_t(각 3회). 26,880행 | 데스크탑 |
| `raw_medium_full.csv` | 중규모 5,760개에서 H5(1회), CSA_f, CSA_t(각 3회). 40,320행 | 데스크탑 |
| `raw_small_rnd.csv` | 소규모 3,840개에서 무작위 수용체 편집 CSA(`csa_f_rnd`, `csa_t_rnd`, 각 3회). 23,040행 | 팀원의 컴퓨터 |
| `소규모_전체_실행_보고서.md` | `raw_small_full.csv`를 정리한 보고서 |

이 파일들에서 `h5`, `csa_f`, `csa_t`, `csa_f_rnd`, `csa_t_rnd`라는 이름은 기준 `first`로 실행한 것을 뜻합니다. 현재의 실행기에서는 같은 이름이 기준 `random`을 뜻하므로 혼동하지 않도록 주의합니다.

## 현재 결과와 비교할 때 주의할 점

- **컴퓨터가 다릅니다.** 시간 제한을 쓰는 실험이어서, 같은 시간 안에 수행하는 CSA의 세대 수가 컴퓨터마다 다릅니다. 중규모에서 데스크탑의 세대 수는 노트북의 약 60%였습니다.
- **`raw_small_rnd.csv`는 세대 수가 특히 적습니다.** 시간 제한까지 실행한 경우의 평균 세대 수가 49로, 같은 방법을 노트북에서 실행했을 때의 약 7분의 1입니다. 한 세대가 오래 걸려서 시간 제한을 최대 83% 넘긴 실행도 있습니다.
- 기준 `first`와 `random`의 차이는 같은 컴퓨터에서 실행한 `results/tiebreak`의 결과로 판단합니다.

## 집계 방법

```bash
python -m experiments.compare_paper --raw results/first/raw_small_full.csv --milp results/milp_small_unlimited.csv
```

```bash
python -m experiments.compare_paper --size medium --raw results/first/raw_medium_full.csv
```

## 다른 폴더와의 관계

- `experiments/analyze.py`는 이 폴더를 읽지 않습니다.
- 처음에는 `results` 바로 아래(`raw_small_full.csv`, `raw_medium_full.csv`)와 `results/rnd`에 있던 파일을 2026년 11월 23일에 이 폴더로 옮겼습니다.
