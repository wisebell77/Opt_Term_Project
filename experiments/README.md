# experiments: 실험 실행과 결과 집계

이 폴더에는 `src`의 알고리즘을 벤치마크 인스턴스에 실행하고 결과를 집계하는 스크립트가 들어 있습니다. 모든 명령은 `codes` 폴더에서 실행합니다.

## 스크립트별 역할

| 파일 | 내용 | 출력 |
|---|---|---|
| `run_milp.py` | MILP로 최적값을 계산합니다. | `results/milp_<크기>.csv` |
| `run.py` | H5, CSA_f, CSA_t, SA_t(냉각 3종)를 실행합니다. | `results/raw_<크기>_<태그>.csv` |
| `analyze.py` | 실행 기록을 읽어 지표를 계산하고 표와 그림을 만듭니다. | `results/summary_*.csv`, `factors_*.csv`, `instances_*.csv`, `wilcoxon.csv`, `fig_rdi.png` |
| `convergence.py` | 인스턴스 하나에서 냉각 방식 3종의 수렴 곡선을 그립니다. | `results/convergence_<인스턴스>.png` |

## 실행 순서

1. 소규모 인스턴스의 최적값을 계산합니다. Gurobi 라이선스가 필요하며, 계산을 마친 `results/milp_small.csv`가 이미 들어 있으므로 다시 실행하지 않아도 됩니다.

```bash
python -m experiments.run_milp --size small
```

2. 실험을 실행합니다.

```bash
python -m experiments.run --size small
```

```bash
python -m experiments.run --size medium
```

3. 결과를 집계합니다.

```bash
python -m experiments.analyze
```

4. 필요한 인스턴스의 수렴 곡선을 그립니다.

```bash
python -m experiments.convergence --instance medium/I_15_2_124_100_T04_R02_1 --evals 200000
```

## run.py의 옵션

| 옵션 | 기본값 | 의미 |
|---|---|---|
| `--size` | 필수 | `small` 또는 `medium` |
| `--methods` | 기본 6개 | 쉼표로 구분한 방법 이름. 기본값은 `h5`, `csa_f`, `csa_t`, `sa_geo`, `sa_log`, `sa_exp`이고, 비교용 변형인 `csa_f_k5`와 `csa_t_k5`는 직접 지정해야 실행됩니다. |
| `--reps` | 5 | 난수를 쓰는 방법의 반복 횟수 |
| `--scale` | 1.0 | 시간 제한 n·m·30/2 밀리초에 곱하는 속도 보정 계수 c |
| `--workers` | 논리 코어 수의 절반 | 동시에 실행하는 프로세스 수 |
| `--shard` | `0/1` | `i/k` 형식이며, 인스턴스를 k개 묶음으로 나눈 것 중 i번째만 실행합니다. |
| `--every` | 1 | k번째 인스턴스마다 하나씩만 실행합니다. 10으로 두면 요인 조합마다 1번 인스턴스만 실행합니다. |
| `--tag` | 컴퓨터 이름 | 결과 파일 이름과 `machine` 열에 기록하는 이름 |

## 여러 노트북에 나누어 실행하는 방법

시간 제한을 사용하는 실험은 컴퓨터의 속도에 영향을 받습니다. 그래서 한 인스턴스에 대한 모든 방법과 모든 반복은 같은 프로세스에서 실행하도록 구현하였고, 노트북 사이에는 인스턴스 단위로만 나눕니다. 세 명이 나누어 실행할 때에는 각자 다음 명령 중 하나를 실행합니다.

```bash
python -m experiments.run --size medium --shard 0/3 --tag a
```

```bash
python -m experiments.run --size medium --shard 1/3 --tag b
```

```bash
python -m experiments.run --size medium --shard 2/3 --tag c
```

실행이 끝나면 각자의 `results/raw_medium_*.csv` 파일을 한 사람의 `results` 폴더에 모은 뒤 `analyze.py`를 실행합니다. 실행을 중단한 뒤 같은 명령을 다시 실행하면, 이미 기록된 (인스턴스, 방법, 반복)은 건너뜁니다.

## 지표의 정의

- **기준값**: MILP의 최적값이 있는 인스턴스는 최적값을, 없는 인스턴스는 실행한 모든 방법이 찾은 최선값을 사용합니다.
- **RPD(%)**: (평균 목적함수값 − 기준값) / 기준값 × 100입니다. 기준값이 0인 인스턴스는 정의할 수 없으므로 제외하고, 그 인스턴스들은 절대 차이(`gap0_mean`)로 따로 집계합니다.
- **RDI(%)**: (평균 목적함수값 − 최선) / (최악 − 최선) × 100이며, 최선과 최악은 비교한 방법들 사이에서 정합니다. 모든 방법의 값이 같으면 0입니다.
- **hit_rate**: 기준값과 같은 목적함수값을 얻은 실행의 비율입니다.
- 난수를 쓰는 방법은 인스턴스별로 반복 실행의 평균 목적함수값을 사용합니다.

## 실행 중 자동 검사

`run.py`는 모든 결과에 대해 해의 유효성을 검사하고, `results/milp_<크기>.csv`가 있으면 목적함수값이 최적값보다 작지 않은지도 검사합니다. 검사에 실패하면 오류를 내고 멈춥니다.

## 다른 폴더와의 관계

- `src`: 알고리즘(`h5`, `csa_f`, `csa_t`, `sa_t`, `solve_milp`)과 실행 예산(`Budget`, `time_limit_seconds`)을 불러와 사용합니다.
- `data`: `src/instance.py`의 `list_instances`와 `load_instance`를 거쳐 인스턴스를 읽습니다.
- `results`: 모든 출력 파일을 이 폴더에 기록합니다. `analyze.py`는 이 폴더의 `raw_*.csv`와 `milp_*.csv`를 읽습니다.
- `tests`: `tests/test_experiments.py`가 이 폴더의 함수를 검증합니다.
