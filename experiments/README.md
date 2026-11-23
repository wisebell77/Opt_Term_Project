# experiments: 실험 실행과 결과 집계

이 폴더에는 `src`의 알고리즘을 벤치마크 인스턴스에 실행하고 결과를 집계하는 스크립트가 들어 있습니다. 모든 명령은 `codes` 폴더에서 실행합니다.

## 스크립트별 역할

| 파일 | 내용 | 출력 |
|---|---|---|
| `run_milp.py` | MILP로 최적값을 계산합니다. | `results/milp_<크기>.csv` |
| `run.py` | H5, CSA, SA_t를 실행합니다. | `results/raw_<크기>_<태그>.csv` |
| `analyze.py` | 실행 기록을 읽어 방법별 지표를 계산하고, 방법을 짝지어 비교합니다. | `results/summary_*.csv`, `factors_*.csv`, `instances_*.csv`, `wilcoxon.csv`, `fig_rdi.png` |
| `compare_paper.py` | H5, CSA_f, CSA_t의 ARDI를 논문의 표 2(소규모), 표 3(중규모)과 요인별로 비교합니다. | 화면 출력 |
| `convergence.py` | 인스턴스 하나에서 냉각 방식 3종의 수렴 곡선을 그립니다. | `results/convergence_<인스턴스>.png` |
| `analyze_tiebreak.py` | 동점 처리 기준 실험의 결과를 기준별로 비교합니다. | 화면 출력 |
| `diagnose_csa.py` | 수용체 편집 방식과 동점 기준에 따라 CSA의 기억 집합과 클론이 얼마나 다양한지 측정합니다. | `results/diagnostics/csa_diversity_small.csv` |
| `diagnose_sa.py` | SA_t가 최적값을 찾는 시점, 시간 제한을 줄였을 때의 결과, 하강만 했을 때의 결과를 측정합니다. | `results/diagnostics/sa_budget_small.csv` |

## 방법 이름

`run.py`의 `--methods`에 쉼표로 구분하여 적습니다.

| 이름 | 방법 |
|---|---|
| `h5` | 건설적 휴리스틱 H5 |
| `csa_f`, `csa_t` | CSA(논문의 서술 그대로). `csa_t`는 초기 기억 집합에 H5의 해를 포함합니다. |
| `csa_f_rnd`, `csa_t_rnd` | 수용체 편집을 수락 검사 없는 무작위 이동으로 바꾼 CSA |
| `csa_f_pct`, `csa_t_pct` | GRASP 제한 목록의 크기를 미배정 작업의 5%로 읽는 CSA |
| `sa_geo`, `sa_log`, `sa_exp` | SA_t의 기하, 로그, 지수 냉각 |
| `sa_exp_cap` | 지수 냉각의 계수를 0.9로 제한한 처음 설계(비교용) |
| `h5_first`, `csa_f_last`, `csa_t_csum` 등 | H5, CSA_f, CSA_t에 동점 처리 기준을 지정한 것. 기준은 `first`, `last`, `csum`, `random`입니다. |

- **이름에 기준이 없는 방법은 팀의 기준인 `random`으로 실행됩니다.** 기준의 뜻과 근거는 `src/README.md`의 "동점 처리 기준"에 있습니다.
- **기준 `random`에서는 H5의 결과도 실행마다 달라지므로**, H5도 다른 방법과 같은 횟수만큼 반복 실행합니다.
- `--methods`를 생략하면 `h5`, `csa_f`, `csa_t`, `sa_geo`, `sa_log`, `sa_exp`를 실행합니다. `--methods tiebreak`라고 쓰면 동점 처리 기준 실험의 12개 방법을 실행합니다.

## 실행 순서

1. 소규모 인스턴스의 최적값을 계산합니다. Gurobi 라이선스가 필요하며, 계산을 마친 `results/milp_small.csv`가 이미 들어 있으므로 다시 실행하지 않아도 됩니다.

```bash
python -m experiments.run_milp --size small
```

2. 실험을 실행합니다. 저장소에 들어 있는 결과는 다음 명령으로 얻은 것입니다.

```bash
python -m experiments.run --size small --methods h5,csa_f,csa_t,csa_f_rnd,csa_t_rnd,sa_geo,sa_log,sa_exp,sa_exp_cap --reps 3 --workers 4 --tag full
```

```bash
python -m experiments.run --size medium --methods h5,csa_f,csa_t,csa_f_rnd,csa_t_rnd,sa_geo,sa_log,sa_exp,sa_exp_cap --reps 3 --workers 4 --tag full
```

3. 결과를 집계합니다.

```bash
python -m experiments.analyze
```

```bash
python -m experiments.compare_paper --size small
```

```bash
python -m experiments.compare_paper --size medium
```

4. 필요한 인스턴스의 수렴 곡선을 그립니다.

```bash
python -m experiments.convergence --instance medium/I_15_2_124_100_T04_R02_1 --evals 200000
```

## run.py의 옵션

| 옵션 | 기본값 | 의미 |
|---|---|---|
| `--size` | 필수 | `small` 또는 `medium` |
| `--methods` | 기본 6개 | 쉼표로 구분한 방법 이름("방법 이름" 참고) |
| `--reps` | 5 | 반복 횟수 |
| `--scale` | 1.0 | 시간 제한 n·m·30/2 밀리초에 곱하는 속도 보정 계수 c |
| `--workers` | 논리 코어 수의 절반 | 동시에 실행하는 프로세스 수. 성능 코어 수 이하로 지정합니다. |
| `--shard` | `0/1` | `i/k` 형식이며, 인스턴스를 k개 묶음으로 나눈 것 중 i번째만 실행합니다. |
| `--every` | 1 | k번째 인스턴스마다 하나씩만 실행합니다. |
| `--tag` | 컴퓨터 이름 | 결과 파일 이름과 `machine` 열에 기록하는 이름 |
| `--out` | `results/raw_<크기>_<태그>.csv` | 결과 파일의 경로 |

실행을 중단한 뒤 같은 명령을 다시 실행하면, 이미 기록된 (인스턴스, 방법, 반복)은 건너뜁니다.

## 여러 컴퓨터에 나누어 실행하는 방법

시간 제한을 사용하는 실험은 컴퓨터의 속도에 영향을 받습니다. 그래서 한 인스턴스에 대한 모든 방법과 모든 반복은 같은 프로세스에서 실행하도록 구현하였고, 컴퓨터 사이에는 인스턴스 단위로만 나눕니다.

```bash
python -m experiments.run --size medium --shard 0/3 --tag a
```

```bash
python -m experiments.run --size medium --shard 1/3 --tag b
```

```bash
python -m experiments.run --size medium --shard 2/3 --tag c
```

실행이 끝나면 각자의 `results/raw_medium_*.csv` 파일을 한 사람의 `results` 폴더에 모은 뒤 `analyze.py`를 실행합니다. 다만 컴퓨터마다 같은 시간 안에 수행하는 세대 수가 다르므로, 방법 사이의 비교는 같은 컴퓨터에서 실행한 결과로 하는 것이 안전합니다. 저장소의 결과는 한 대의 노트북에서 실행한 것입니다.

## 집계와 검정

- **`analyze.py`**는 `results` 폴더 바로 아래의 `raw_*.csv`를 모두 읽습니다. 하위 폴더(`first`, `tiebreak`, `diagnostics`, `pilot`)는 읽지 않습니다.
- **짝 비교**는 인스턴스별 평균 총 지연을 짝지어 Wilcoxon 부호순위 검정으로 합니다. 비교할 짝은 `--pairs`로 정하며, 생략하면 다음을 비교합니다: CSA_f와 CSA_t, CSA_t와 무작위 수용체 편집 CSA_t, CSA_t와 SA_t(기하), 무작위 수용체 편집 CSA_t와 SA_t(기하), 냉각 방식 사이.

```bash
python -m experiments.analyze --pairs csa_t,sa_geo sa_geo,sa_log
```

- **`analyze_tiebreak.py`**는 더 좋은 인스턴스와 더 나쁜 인스턴스의 수만으로 판단하는 부호 검정을 씁니다. Wilcoxon 검정보다 보수적입니다.

## 동점 처리 기준 실험

논문이 정하지 않은 동점을 어떻게 처리하느냐에 따라 결과가 얼마나 달라지는지 확인하는 실험입니다. H5, CSA_f, CSA_t를 기준 네 가지로 실행합니다.

```bash
python -m experiments.run --size small --methods tiebreak --reps 3 --workers 4 --tag tiebreak --out results/tiebreak/raw_small.csv
```

```bash
python -m experiments.analyze_tiebreak --size small
```

- 한 인스턴스의 네 기준은 같은 프로세스에서 이어서 실행되므로, 기준 사이에 컴퓨터의 속도 조건이 같습니다.
- 결과 파일을 `results/tiebreak`에 두는 이유는 본 실험의 집계에 섞이지 않게 하기 위해서입니다.
- `analyze_tiebreak.py`는 기준별 지표, 기준 `first`와의 인스턴스별 비교, 요인별 도달 비율, H5 구성 단계에서 기준에 따라 선택이 달라지는 삽입 결정의 비율을 출력합니다.

## 진단

결과의 원인을 설명하는 지표를 만드는 스크립트입니다. 둘 다 소규모 인스턴스를 대상으로 하며, 결과와 해석은 `results/diagnostics/README.md`에 있습니다.

```bash
python -m experiments.diagnose_csa --workers 4
```

```bash
python -m experiments.diagnose_sa --workers 4
```

## 지표의 정의

- **기준값**: MILP의 최적값이 있는 인스턴스는 최적값을, 없는 인스턴스는 실행한 모든 방법이 찾은 최선값을 사용합니다. 총 지연은 0보다 작을 수 없으므로, 기준값이 0인 인스턴스에서는 0이 최적값입니다.
- **RPD(%)**: (평균 목적함수값 − 기준값) / 기준값 × 100입니다. 기준값이 0인 인스턴스는 정의할 수 없으므로 제외하고, 그 인스턴스들은 절대 차이(`gap0_mean`)로 따로 집계합니다.
- **RDI(%)**: (평균 목적함수값 − 최선) / (최악 − 최선) × 100이며, 최선과 최악은 비교한 방법들 사이에서 정합니다. 모든 방법의 값이 같으면 0입니다.
- **hit_rate**: 기준값과 같은 목적함수값을 얻은 실행의 비율입니다.
- 인스턴스별로 반복 실행의 평균 목적함수값을 사용합니다.

## 실행 중 자동 검사

`run.py`는 모든 결과에 대해 해의 유효성을 검사하고, `results/milp_<크기>.csv`가 있으면 목적함수값이 최적값보다 작지 않은지도 검사합니다. 검사에 실패하면 오류를 내고 멈춥니다.

## 다른 폴더와의 관계

- `src`: 알고리즘(`h5`, `csa_f`, `csa_t`, `sa_t`, `solve_milp`), 동점 처리 기준(`tiebreak`), 실행 예산(`Budget`, `time_limit_seconds`)을 불러와 사용합니다.
- `data`: `src/instance.py`의 `list_instances`와 `load_instance`를 거쳐 인스턴스를 읽습니다.
- `results`: 모든 출력 파일을 이 폴더에 기록합니다.
- `tests`: `tests/test_experiments.py`, `tests/test_tiebreak.py`, `tests/test_diagnose.py`가 이 폴더의 함수를 검증합니다.
