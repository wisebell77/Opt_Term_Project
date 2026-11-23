# results: 실험 결과

이 폴더에는 `experiments`의 스크립트가 만든 결과 파일이 저장됩니다.

## 구성

| 위치 | 내용 |
|---|---|
| 이 폴더 바로 아래 | 본 실험의 결과. 팀의 동점 처리 기준(`random`)으로 한 대의 노트북에서 실행한 것입니다. |
| `tiebreak/` | 동점 처리 기준 네 가지를 비교한 실험 |
| `diagnostics/` | 결과의 원인을 설명하는 진단(CSA의 다양성, SA_t의 탐색 여유) |
| `first/` | 기준을 정하기 전에 기준 `first`로 실행한 이전 결과 |
| `pilot/` | `main` 브랜치의 이전 구현으로 얻은 예비 결과 |

각 하위 폴더의 `README.md`에 실행 조건과 결과의 해석이 있습니다. 본 실험의 결과와 해석은 상위 폴더의 `README.md`에 정리되어 있습니다.

## 이 폴더 바로 아래의 파일

| 파일 | 만드는 스크립트 | 내용 |
|---|---|---|
| `milp_small.csv` | `experiments/run_milp.py` | 소규모 인스턴스별 MILP 결과(제한 시간 100초) |
| `milp_small_unlimited.csv` | `experiments/run_milp.py` | 제한 시간 없이 푼 MILP 결과. 3,840개 모두 최적임이 증명되었습니다. |
| `raw_small_full.csv` | `experiments/run.py` | 소규모 전체의 실행 기록. 실행 한 번이 한 행입니다. |
| `raw_medium_full.csv` | `experiments/run.py` | 중규모 전체의 실행 기록 |
| `summary_<크기>.csv` | `experiments/analyze.py` | 방법별 요약 지표 |
| `factors_<크기>.csv` | `experiments/analyze.py` | 요인(n, m, 준비시간, p, τ, R)의 수준별 지표 |
| `instances_<크기>.csv` | `experiments/analyze.py` | (인스턴스, 방법)별 지표 |
| `wilcoxon.csv` | `experiments/analyze.py` | 방법을 짝지어 비교한 결과 |
| `fig_rdi.png` | `experiments/analyze.py` | 방법별 평균 RDI 막대 그림 |
| `convergence_<인스턴스>.png` | `experiments/convergence.py` | 냉각 방식 3종의 수렴 곡선 |

`milp_small.csv`와 `milp_small_unlimited.csv`의 목적함수값은 모든 인스턴스에서 같습니다. 앞의 파일에서는 3개 인스턴스가 제한 시간 안에 최적임이 증명되지 않았을 뿐입니다.

## 열 설명

`milp_<크기>.csv`

| 열 | 의미 |
|---|---|
| `instance` | 인스턴스 이름 |
| `objective` | MILP가 찾은 총 순수지연시간 |
| `optimal` | 시간 제한 안에 최적임이 증명되었으면 True |
| `bound` | 하한 |
| `runtime` | 풀이 시간(초) |

`raw_<크기>_<태그>.csv`

| 열 | 의미 |
|---|---|
| `instance`, `size` | 인스턴스 이름과 크기 구분 |
| `n`, `m`, `setup`, `p`, `tau`, `R`, `idx` | 파일명에서 읽은 요인과 인스턴스 번호 |
| `method` | 방법 이름. 목록은 `experiments/README.md`의 "방법 이름"에 있습니다. |
| `rep`, `seed` | 반복 번호와 그 실행에 사용한 시드 |
| `objective` | 총 순수지연시간 |
| `elapsed` | 실행 시간(초) |
| `iterations` | CSA는 세대 수, SA_t는 이웃 해 평가 횟수 |
| `time_limit` | 적용한 시간 제한(초) |
| `machine` | 실행을 구분하는 이름(`--tag`) |

요약 파일의 지표(`rpd_mean`, `gap0_mean`, `rdi_mean`, `hit_rate`)는 `experiments/README.md`의 "지표의 정의"에 설명되어 있습니다.

## 다른 폴더와의 관계

- `experiments`의 스크립트만 이 폴더에 파일을 기록합니다. 저장 위치는 `src/instance.py`의 `RESULTS_DIR`로 정해집니다.
- `experiments/run.py`는 이 폴더의 `milp_<크기>.csv`를 읽어, 실험 결과가 최적값보다 작게 나오는 오류가 없는지 검사합니다.
- `experiments/analyze.py`는 이 폴더 바로 아래의 `raw_*.csv`와 `milp_*.csv`만 읽어 요약 파일을 만듭니다. 하위 폴더는 읽지 않습니다.
