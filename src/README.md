# src: 알고리즘 모듈

이 폴더에는 문제의 자료 구조와 모든 알고리즘이 들어 있습니다. 실험을 실행하거나 결과를 집계하는 코드는 이 폴더에 두지 않습니다.

## 파일별 역할

| 파일 | 내용 |
|---|---|
| `instance.py` | 인스턴스 자료 구조(`Instance`), 벤치마크 파일 파서(`load_instance`, `list_instances`, `parse_name`), 폴더 경로(`DATA_DIR`, `RESULTS_DIR`) |
| `schedule.py` | 해 표현(`Schedule`), 기계별 비용 계산(`machine_cost`, `job_tardiness`), 유효성 검사(`validate`) |
| `insertion.py` | 삽입 연산 `best_position`(BestPosition)과 `best_position_total`(BestPosition_Total) |
| `h5.py` | 건설적 휴리스틱 H5: 구성(`construct`), 보정(`repair`), 개선(`improve`) |
| `csa.py` | 클론 선택 알고리즘 `csa_f`, `csa_t`와 그 구성 요소(GRASP, 이웃 연산자, VND, 적합도, 재선택) |
| `sa.py` | 개선 방법 `sa_t`와 냉각 방식 3종(`geo`, `log`, `exp`), 온도 설정 |
| `milp.py` | Gurobi로 푸는 MILP 모형 `solve_milp` |
| `budget.py` | 실행 예산 `Budget`(시간 제한 또는 반복 횟수), 시간 제한 계산(`time_limit_seconds`), 실행 결과 `Result` |

## 모듈 사이의 의존 관계

```
instance  →  schedule  →  insertion  →  h5  →  csa
                                         └──→  sa
budget  →  csa, sa
schedule  →  milp
```

화살표의 오른쪽 모듈이 왼쪽 모듈을 불러옵니다. `milp.py`만 `gurobipy`를 사용하고, 나머지 모듈은 Python 표준 라이브러리만 사용합니다.

## 공통 규칙

- 작업과 기계의 번호는 0부터 시작합니다. `p[i][j]`는 기계 i에서 작업 j의 가공시간이고, `s[i][j][k]`는 기계 i에서 작업 j 바로 다음에 작업 k를 처리할 때의 준비시간입니다.
- 해는 기계별 작업 순서 리스트(`Schedule.seqs`)입니다. 순서를 바꿀 때에는 반드시 `Schedule.set_machine`을 사용해야 저장된 비용이 함께 갱신됩니다.
- 각 기계의 첫 작업에는 준비시간이 없습니다.
- 탐색 알고리즘은 모두 `algorithm(inst, rng, budget)` 형태로 호출하고 `Result`를 돌려줍니다. `rng`는 `random.Random(seed)` 객체이며, 전역 난수 함수는 사용하지 않습니다.
- 동점 처리 규칙은 다음과 같습니다. 지연 합이 같으면 완료시간 합이 작은 쪽을 고르고, 그래도 같으면 기계 번호와 위치가 작은 쪽을 고릅니다.

## CSA 세부 규칙의 근거

대상 논문(Perez-Gonzalez et al., 2019)의 6절은 CSA를 요약만 하고, 세부는 CSA의 원 논문인 Diana et al.(2015)에 넘깁니다. 그래서 대상 논문이 적지 않은 부분은 Diana et al.(2015)의 3절과 4절을 따랐습니다. 조사 내용은 상위 폴더의 `reports/CSA 구현 근거 출처 조사.md`에 있습니다.

| 항목 | 구현 | 근거 |
|---|---|---|
| 수용체 편집 | U[1, 2]회의 무작위 외부 삽입이며, 수락 검사를 하지 않음 | Diana et al.(2015) 3.3.1절 |
| VND | 내부 교환, 외부 삽입, 외부 교환의 순서이며, 개선되면 첫 이웃으로 돌아감 | Diana et al.(2015) Algorithm 2 |
| 이웃 탐색 | 기계 쌍 안의 최선 이동을 총 지연이 줄어드는 경우에만 적용 | Diana et al.(2015) Algorithm 3–5 |
| GRASP 제한 목록의 크기 | 미배정 작업의 5% | Diana et al.(2015) 표 1, 표 2 |
| 재선택 | 같은 해는 한 번만 남기고, 목적함수가 같은 해의 순서는 무작위로 정함 | Diana et al.(2015) 3절, 3.4절 |
| 우선도 | 부모보다 개선된 클론은 100, 개선되지 않은 해는 세대마다 5씩 감소 | Diana et al.(2015) 3.2절 |
| 적합도, 복제, 거리, 시간 제한, 파라미터 값 | 대상 논문의 서술과 같음 | 대상 논문 6절, 8절 |

## 어느 논문에도 없어 본 프로젝트가 정한 규칙

| 규칙 | 위치 |
|---|---|
| 지연 합이 같을 때의 동점 처리(논문은 BestPosition에서 삽입 전후의 지연이 0인 경우만 명시) | `insertion.py`, `csa.py` |
| 그룹 안에서는 납기 오름차순(EDD)으로 처리(논문의 의사코드와 본문의 표기가 서로 어긋남) | `h5.construct` |
| 보정 단계에서 대상 작업의 지연이 0이면 이동하지 않음 | `h5.repair` |
| CSA_t의 초기 기억 집합은 H5 해 1개와 GRASP 해 19개 | `csa.csa` |
| 무작위 외부 삽입은 적격 기계가 2대 이상인 작업, 다른 적격 기계, 위치를 균등하게 선택 | `csa.random_ext_insert` |
| 제한 목록의 크기는 5%를 올림하며 최소 1개 | `csa.rcl_size` |
| 우선도의 하한은 0이며, 0에 도달한 해를 제거하지 않음 | `csa.csa` |
| 총 지연이 0인 해를 찾으면 즉시 종료 | `csa.csa`, `sa.sa_t` |
| 시간 제한에는 초기해 생성 시간을 포함 | `csa.csa`, `sa.sa_t` |

## GRASP 제한 목록의 크기에 관한 주의

Diana et al.(2015)은 제한 목록의 크기 k를 미배정 작업에 대한 비율(5%)로 정의하고, 대상 논문은 "k개의 최선 작업"(k = 5)이라고 적습니다. 대상 논문의 저자들이 어느 쪽으로 구현했는지는 확인할 수 없어서, 두 해석을 소규모 인스턴스 384개에서 5회씩 실행하여 원저자의 공개 결과와 비교하였습니다.

| 최적 도달 비율 | CSA_t | CSA_f |
|---|---|---|
| 원저자의 실행(소규모 전체) | 84.4% | 76.2% |
| 5%로 읽은 경우 | 98.2% | 96.9% |
| 5개로 읽은 경우 | 99.4% | 99.5% |

5%로 읽은 경우가 원저자의 결과에 더 가깝고, 논문처럼 CSA_t가 CSA_f보다 좋게 나오므로 5%를 기본값으로 정하였습니다. 5개로 읽는 변형은 `csa_f`와 `csa_t`의 `rcl_percent=False` 인자, 또는 실험 실행기의 `csa_f_k5`와 `csa_t_k5`로 실행할 수 있습니다.

5% 해석에서는 미배정 작업이 20개 이하이면 목록에 작업이 하나만 들어갑니다. 따라서 작업 수가 20 이하인 인스턴스에서 GRASP는 결정적인 탐욕 구성이 되고, CSA_f의 초기 기억 집합은 같은 해 20개로 시작합니다.

## 다른 폴더와의 관계

- `data`: `instance.py`가 `data/small`과 `data/medium`의 파일을 읽습니다. 경로는 `instance.py` 파일의 위치를 기준으로 계산하므로, `codes` 폴더를 어디에 두어도 동작합니다.
- `experiments`: 이 폴더의 알고리즘을 불러와 실행하고, 결과를 `results`에 기록합니다. `src`는 `experiments`를 불러오지 않습니다.
- `tests`: 이 폴더의 모든 모듈을 검증합니다. 모듈을 수정한 뒤에는 `codes` 폴더에서 `python -m pytest`를 실행하여 확인합니다.
