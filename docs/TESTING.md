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

근거: [uv export/build](https://docs.astral.sh/uv/reference/cli/),
[Python isolated mode](https://docs.python.org/3.12/using/cmdline.html#cmdoption-I).
