# 추천 서버 검증

Python 3.12와 CI에 고정한 uv로 `./scripts/check.sh`를 실행한다. 저장소 비밀정보/생성물 검사,
잠금 의존성 설치, Ruff 정적 검사/포맷, 서비스 경계 테스트, 배포 산출물 검증을 같은 순서로 수행한다.
PR·main push·수동 실행의 필수 `recommendation-ci`가 이 검증을 실행한다.

## 배포 산출물 검증

`uv run --locked python scripts/smoke_distribution.py`는 아래를 확인한다.

1. 빈 임시 디렉터리에 sdist와 wheel을 새로 빌드한다. 기존 `dist/`에 남은 오래된 wheel을 선택하지 않는다.
2. `uv export --locked --no-dev --no-default-groups --no-emit-project --no-sources`로 runtime 요구사항을 추출한다.
3. 임시 venv에 해시 검증한 잠금 runtime 의존성만 설치하고, 방금 빌드한 wheel을 `--no-deps`로 설치한다.
4. `uv pip check`로 배포 메타데이터의 의존성 정합성을 확인한다.
5. checkout 밖에서 `python -I`로 import 경로가 임시 환경에 있는지 확인하고 실제 Uvicorn을 실행한다.
6. OS가 할당한 loopback 포트에서 `/health`·`/openapi.json`과 B0 추천 POST를 검증한다.
   조건을 요구하는 미확인 가격·판매 불가 후보가 제외되고, 중복 ID 요청은 422인지 확인한다.
7. 새 wheel의 runtime-only `python -I`로 `content_experiment`를 실제 실행한다. 직접 작성한
   fixture의 vocabulary/IDF·수치 fit과 명시 상품군 분리·필수 조건 결과를 확인한다. 원문/모델을
   Git이나 artifact에 업로드하지 않으며 실제 상품 품질 평가로 표현하지 않는다.
8. `legacy_seed_audit`도 runtime-only 실제 CLI로 작은 자체 SQL literal/바이트 시그니처를
   감사한다. 실제80행/이미지는 CI가 읽지 않으며 결과가 자동 학습 승격을 만들지 않는지 확인한다.

HTTP 과정에 DB·AWS·모델·외부 AI API 환경변수를 전달하지 않는다. 8000 포트를 점유하지 않고
본인 서버 프로세스와 임시 환경만 정리한다. 현재 검증 대상은 Linux/macOS이며 CI는 Ubuntu다.
성공한 새 배포 파일은 로컬 `dist/`에 보존한다. 생성물·runtime 요구사항·서버 로그는 Git에 추가하지 않는다.
CI는 성공/실패와 무관하게 JUnit과 단계/결과만 담은 smoke JSON을 artifact로 7일 보관한다.
원문 서버 로그·실제 환경변수·venv·데이터는 artifact에 포함하지 않는다. 보고서는 로컬 `reports/`에 생성되며 무시된다.

이 검증은 패키징 누락·checkout의 소스/개발 의존성에 대한 숨은 의존·실제 HTTP 계약 회귀를
확인한다. B0 계약의 기능 검증은 학습 모델·실제 사용자 선호 품질·Backend 통합 검증을 뜻하지 않는다.

## B0 추천 계약의 회귀 검증

`tests/test_baseline.py`는 직접 작성한 가상 입력으로 판매 상태·주종·가격/도수 범위·제외 조건,
unknown과 0의 구분, 후보 부족 시 조건 유지, 필터 뒤 limit, 입력 순열과 무관한 결과를 확인한다.
잘못된 타입·범위/상한·중복 ID·미지정 필드, 512 KiB 원문/ASGI 누적 크기 제한과 비유한 수치
입력의 JSON 오류 응답도 검증한다. fixture 값은 실제 상품 사실·사용자 행동·평가 정답이 아니다.
기본 기준선은 학습 전 비교 대상으로 구현한 신규 기능이며 과거 모델의 장애/성능 개선으로 쓰지 않는다.

## 오프라인 원천 감사

`tests/test_catalog_audit.py`는 직접 작성한 가상 entity로 권리 보류를 입력 읽기 전에 확인하는지,
단위 변환·범위/문맥/다중 값의 unknown·deprecated·라벨 누락·브랜드/SKU 분리·원문 해시와
검수 mapping·명시 Backend ID/그룹/시연 가용성·가격·B0 계약·출력 덮어쓰기 차단을 검증한다.
실제 CC0 소량 표본 감사와 이 회귀 fixture는 구분하며 CI가 원천을 다운로드하지 않는다.
격리 wheel 검증은 checkout 밖에서 CLI `--help`도 실행해 runtime 의존성/패키징을 확인한다.

`tests/test_legacy_seed_audit.py`는 작은 직접 작성 SQL·로컬 바이트 fixture로 활성 INSERT/주석·
quoted text·컬럼/리터럴 상한·지원 불가/변경문 거절, 사용자/암호 행 비노출, Decimal 타입/정확값·
unknown/실제0·언더플로, 웹 매핑·경로/시그니처/해시·중복·symlink/파일 크기와 새 출력 보존을 검증한다.
DB/SQL 실행·네트워크·실제 이미지 변환·학습은 수행하지 않는다. 실제80행 관측 집계와 단위 테스트의
고정 정답을 결합하지 않으며 [감사 범위·실제 결과](LEGACY-SEED-AUDIT.md)를 별도로 관리한다.

## 독립 고정 시나리오

단위 테스트 뒤 `scripts/evaluate_baseline.py`가 버전 고정 fixture를 ASGI 앱으로 실행하고,
`scenario_evaluation`이 생산용 점수/필터 helper와 분리해 결과를 검사한다. `tests/test_scenario_evaluation.py`는
명세 모순·해시/알고리즘·케이스 누락/중복·변조된 결과·제약/이유/순서·CLI 보호와 미래 모델의
제약 전용 정책을 검증한다. 기대값을 실행 결과로 만들지 않으며 Recall/NDCG는 미산출이다.

CI는 `reports/baseline-scenarios.json` 요약만 업로드하고 `baseline-responses.json`은 보관하지 않는다.
새 wheel에서는 runtime-only `scenario_evaluation --help`를 실행한다. 명세/정책과 한계는
[EVALUATION.md](EVALUATION.md)를 따른다. 이 ASGI runner는 실제 서버 간 통합 E2E가 아니다.

## B1 오프라인 fit·누수 경계

`tests/test_content_model.py`는 vocabulary/수동 계산 IDF·관측 수치 범위의 실제 fit,
한국어 한 글자/띄어쓰기 태그·맛/향 namespace, fit 미호출 transform, unknown과 실제0·분모/기여,
상수/결측 열 비활성화·빈/OOV/zero-vector fallback, 필수/제외·동점/순열·선택 상품 제외,
엄격 타입/상한과 상품군 교차/미지정·수동 기대 사실 모순·CLI 출력 보존을 검증한다.

필수 CI와 `check.sh`의 `scripts/evaluate_content.py`는 허구11상품을 학습4/3그룹·변환7/6그룹으로
나누어 8개 계약 시나리오를 실제 실행한다. 학습에 없는 태그·수치가 vocabulary/범위에 유입되지
않는지 확인한다. `reports/content-fit-summary.json`만 7일 보관하고 원문·응답·어휘/IDF는 제외한다.
고정 fixture의 B0/B1 순서 비교는 품질 개선이나 최종 holdout이 아니다. 독립 관련성 라벨이 없어
Recall/NDCG는 미산출이며 사용자 선호 학습·실서비스 카탈로그 fit·HTTP B1/Backend 통합은 남아 있다.
[모듈·수식·실행 경계](CONTENT-MODEL.md)를 따른다.

근거: [uv export/build](https://docs.astral.sh/uv/reference/cli/),
[Python isolated mode](https://docs.python.org/3.12/using/cmdline.html#cmdoption-I).
