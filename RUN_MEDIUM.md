# 중규모 인스턴스 실행 안내 (`paper-faithful` 브랜치)

이 문서의 순서대로 진행하면, 저장소를 받는 것부터 중규모 인스턴스 5,760개를 실행하고 결과를 저장소에 올리는 것까지 마칠 수 있습니다.

- 저장소: `https://github.com/wisebell77/Opt_Term_Project.git`
- 브랜치: `paper-faithful`

## 빠른 실행

이미 Python과 필요한 패키지가 설치되어 있다면 아래 명령만 차례로 실행하면 됩니다. 각 단계의 설명은 뒤에 있습니다.

```bash
git clone -b paper-faithful https://github.com/wisebell77/Opt_Term_Project.git codes
cd codes
python -m pytest
python -m experiments.run --size medium --methods h5,csa_f,csa_t --reps 3 --workers 5 --tag full
python -m experiments.compare_paper --size medium
git add results/raw_medium_full.csv
git commit -m "중규모 전체 실행 결과 추가"
git push origin paper-faithful
```

## 실행하는 내용

| 항목 | 내용 |
|---|---|
| 인스턴스 | `data/medium`의 5,760개(n = 15, 20, 25, 30, 35, 40 / m = 2, 4, 6, 8) |
| 방법 | H5(1회), CSA_f와 CSA_t(각 3회). 소규모 전체 실행과 같은 조건입니다. |
| 처리 기준 | 이 브랜치의 기준입니다. 제한 목록은 작업 5개, 수용체 편집은 개선될 때만 이동, 재선택은 중복 허용, 완료시간 합 동점 처리는 지연이 0인 경우에만 적용합니다. 자세한 내용은 `src/README.md`에 있습니다. |
| 시간 제한 | 실행마다 n·m·15밀리초(0.45초–4.8초). 총 지연이 0인 해를 찾으면 바로 끝납니다. |
| MILP | 중규모에서는 풀지 않습니다. |
| 결과 파일 | `results/raw_medium_full.csv` |

## 1. 저장소 준비

처음 받는 경우에는 다음 명령을 실행합니다. 인스턴스 파일이 함께 들어 있어서 약 100MB를 받습니다.

```bash
git clone -b paper-faithful https://github.com/wisebell77/Opt_Term_Project.git codes
cd codes
```

이미 받아 둔 폴더가 있으면 그 폴더에서 최신 상태로 맞춥니다.

```bash
git fetch origin
git switch paper-faithful
git pull
```

이후의 모든 명령은 이 폴더(`codes`)에서 실행합니다.

## 2. Python 환경

Python 3.9 이상이 필요합니다. 소규모를 실행했던 환경이 그대로 있으면 이 단계는 건너뛰어도 됩니다.

가상 환경을 새로 만들려면 다음과 같이 합니다.

macOS 또는 Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows(명령 프롬프트):

```bat
python -m venv .venv
.venv\Scripts\activate.bat
```

패키지를 설치합니다. 중규모 실행에는 Gurobi가 필요하지 않습니다.

```bash
pip install pandas scipy matplotlib pytest
```

## 3. 설치 확인

```bash
python -m pytest
```

실패(failed)가 없으면 됩니다. Gurobi를 쓸 수 없는 환경에서는 MILP 테스트가 건너뜀(skipped)으로 표시되며, 이것은 정상입니다.

## 4. 실행

```bash
python -m experiments.run --size medium --methods h5,csa_f,csa_t --reps 3 --workers 5 --tag full
```

- **`--workers`**: 동시에 실행하는 프로세스 수입니다. 컴퓨터의 성능 코어 수 이하로 지정합니다. 프로세스가 너무 많으면 같은 시간 제한 안에 수행하는 세대 수가 줄어듭니다.
- **소요 시간**: 성능 코어 4개인 노트북에서 프로세스 4개로 약 10분이 걸릴 것으로 추정합니다(인스턴스의 13분의 1을 실행한 시간으로 계산한 값입니다).
- **진행 표시**: `  400/5760`과 같이 끝난 인스턴스 수가 출력됩니다.
- **중단과 재개**: 중간에 멈추어도 같은 명령을 다시 실행하면, 이미 기록된 부분은 건너뛰고 이어서 실행합니다.
- **처음부터 다시 실행**: `results/raw_medium_full.csv`를 지운 뒤 같은 명령을 실행합니다.
- **주의**: 시간 제한을 쓰는 실험이므로, 실행하는 동안 같은 컴퓨터에서 다른 무거운 작업을 하지 않습니다.

실행기는 모든 해의 유효성(모든 작업이 정확히 한 번, 적격 기계에 배정되었는지)을 검사합니다. 검사에 실패하면 오류를 내고 멈춥니다.

## 5. 결과 확인

기록이 모두 들어갔는지 확인합니다. 행 수는 40,320(= 5,760 × 7), 인스턴스 수는 5,760이어야 합니다.

```bash
python -c "import csv; rows = list(csv.DictReader(open('results/raw_medium_full.csv', newline=''))); print(len(rows), len({r['instance'] for r in rows}))"
```

논문의 표 3과 비교합니다.

```bash
python -m experiments.compare_paper --size medium
```

이 명령은 다음을 출력합니다.

- 요인 수준별 ARDI(H5, CSA_f, CSA_t)와 논문 표 3의 값
- 기준값에 도달한 인스턴스의 비율과 평균 실행 시간
- CSA_t와 CSA_f의 인스턴스별 비교

해석할 때 주의할 점은 두 가지입니다.

- 중규모는 MILP 결과가 없으므로, 기준값은 실행한 방법들이 찾은 최선값입니다. 최적값이라는 보장은 없습니다.
- 논문의 ARDI는 19개 방법으로 계산한 값이어서, 절대 수치는 직접 비교할 수 없습니다. 방법의 순서와 요인별 경향을 비교합니다.

## 6. 결과 올리기

```bash
git add results/raw_medium_full.csv
git commit -m "중규모 전체 실행 결과 추가"
git push origin paper-faithful
```

푸시하려면 이 컴퓨터에서 GitHub에 로그인되어 있어야 합니다.

## 선택: SA_t도 함께 실행

SA_t(냉각 방식 3종)까지 실행하려면 방법 목록에 추가합니다. 같은 태그를 쓰면 같은 파일에 이어서 기록되고, 이미 끝난 실행은 건너뜁니다.

```bash
python -m experiments.run --size medium --methods h5,csa_f,csa_t,sa_geo,sa_log,sa_exp --reps 3 --workers 5 --tag full
```

SA_t까지 실행한 뒤의 집계는 `python -m experiments.analyze`를 사용합니다. `compare_paper`는 H5, CSA_f, CSA_t만 다룹니다.

## 문제가 생기면

| 증상 | 확인할 점 |
|---|---|
| `No module named 'src'` | `codes` 폴더에서 `python -m ...` 형식으로 실행했는지 확인합니다. |
| `No module named 'pandas'` 등 | 2번의 패키지 설치를 실행했는지, 가상 환경이 켜져 있는지 확인합니다. |
| `AssertionError`로 멈춤 | 해의 유효성 검사에 실패한 것입니다. 다시 실행하지 말고 오류 메시지를 그대로 팀에 공유합니다. |
| 행 수가 40,320보다 적음 | 실행이 중간에 멈춘 것입니다. 4번의 명령을 다시 실행하면 이어서 실행합니다. |
