# results: 실험 결과

이 폴더에는 `experiments`의 스크립트가 만든 결과 파일이 저장됩니다. 사람이 직접 수정하는 파일은 없습니다.

## 파일 목록

| 파일 | 만드는 스크립트 | 내용 |
|---|---|---|
| `milp_<크기>.csv` | `experiments/run_milp.py` | 인스턴스별 MILP 결과 |
| `raw_<크기>_<태그>.csv` | `experiments/run.py` | 실행 한 번이 한 행인 원본 기록 |
| `summary_<크기>.csv` | `experiments/analyze.py` | 방법별 요약 지표 |
| `factors_<크기>.csv` | `experiments/analyze.py` | 요인(n, m, 준비시간, p, τ, R)의 수준별 지표 |
| `instances_<크기>.csv` | `experiments/analyze.py` | (인스턴스, 방법)별 지표 |
| `wilcoxon.csv` | `experiments/analyze.py` | 두 방법의 짝 비교 결과 |
| `fig_rdi.png` | `experiments/analyze.py` | 방법별 평균 RDI 막대 그림 |
| `convergence_<인스턴스>.png` | `experiments/convergence.py` | 냉각 방식 3종의 수렴 곡선 |

`tiebreak` 폴더에는 동점 처리 기준 실험의 실행 기록과 결과 정리가 들어 있으며, `analyze.py`는 이 폴더를 읽지 않습니다.

`milp_small.csv`는 소규모 인스턴스 3,840개의 계산을 마친 파일이 이미 들어 있습니다. `pilot` 폴더에는 코드 구현 직후에 수행한 예비 실행의 결과가 참고용으로 들어 있으며, `analyze.py`는 이 폴더를 읽지 않습니다.

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
| `method` | `h5`, `csa_f`, `csa_t`, `sa_geo`, `sa_log`, `sa_exp` |
| `rep`, `seed` | 반복 번호와 그 실행에 사용한 시드 |
| `objective` | 총 순수지연시간 |
| `elapsed` | 실행 시간(초) |
| `iterations` | CSA는 세대 수, SA는 이웃 해 평가 횟수 |
| `time_limit` | 적용한 시간 제한(초) |
| `machine` | 실행한 컴퓨터의 이름(`--tag`) |

요약 파일의 지표(`rpd_mean`, `gap0_mean`, `rdi_mean`, `hit_rate`)는 `experiments/README.md`의 "지표의 정의"에 설명되어 있습니다.

## 다른 폴더와의 관계

- `experiments`의 스크립트만 이 폴더에 파일을 기록합니다. 저장 위치는 `src/instance.py`의 `RESULTS_DIR`로 정해집니다.
- `experiments/run.py`는 이 폴더의 `milp_<크기>.csv`를 읽어, 실험 결과가 최적값보다 작게 나오는 오류가 없는지 검사합니다.
- `experiments/analyze.py`는 이 폴더의 `raw_*.csv`와 `milp_*.csv`를 읽어 요약 파일을 만듭니다.
- 여러 노트북에서 나누어 실행한 경우에는 각자의 `raw_*.csv` 파일을 한 사람의 이 폴더에 모은 뒤 집계합니다.
