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
6. OS가 할당한 loopback 포트에서 `/health` 응답과 `/openapi.json`의 JSON health 계약을 검증한다.

HTTP 과정에 DB·AWS·모델·외부 AI API 환경변수를 전달하지 않는다. 8000 포트를 점유하지 않고
본인 서버 프로세스와 임시 환경만 정리한다. 현재 검증 대상은 Linux/macOS이며 CI는 Ubuntu다.
성공한 새 배포 파일은 로컬 `dist/`에 보존한다. 생성물·runtime 요구사항·서버 로그는 Git에 추가하지 않는다.
CI는 성공/실패와 무관하게 JUnit과 단계/결과만 담은 smoke JSON을 artifact로 7일 보관한다.
원문 서버 로그·실제 환경변수·venv·데이터는 artifact에 포함하지 않는다. 보고서는 로컬 `reports/`에 생성되며 무시된다.

이 검증은 패키징 누락·checkout의 소스/개발 의존성에 대한 숨은 의존·실제 HTTP 계약 회귀를
확인한다. 추천 모델 품질·성능이나 아직 없는 추천 API를 검증했다고 표현하지 않는다.

근거: [uv export/build](https://docs.astral.sh/uv/reference/cli/),
[Python isolated mode](https://docs.python.org/3.12/using/cmdline.html#cmdoption-I).
