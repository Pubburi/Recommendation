# 배포 산출물 테스트·CI 보강

- 기존 검증은 소스 checkout에서 TestClient health와 wheel 빌드까지만 수행했다.
- fresh build → runtime-only 잠금 설치 → wheel no-deps 설치 → 의존성/격리 import → 실제 HTTP/OpenAPI 검증으로 배포 경계를 확인한다.
- scripts/check.sh와 필수 recommendation-ci에 같은 smoke를 연결하고 기존 lint/pytest/빌드를 유지한다.
- 성공/실패 확인을 위해 JUnit과 단계/상태 JSON만 7일 artifact로 보관하고 원문 서버 로그·venv·데이터는 제외한다.
- 기존 dist의 오래된 wheel을 선택하지 않으며 임시 포트/환경과 본인 프로세스만 사용한다. DB/AWS/모델과 다른 레포를 수정하지 않는다.
- 이 변경은 검증 보강이다. 추천 모델 구현·서비스 성능 개선이나 새 README 사례를 확보했다고 집계하지 않는다.
- 로컬 Python 3.12.14·uv 0.13.6에서 전체 check.sh(Ruff·pytest·패키지 설치/HTTP) 통과. macOS 경로 별칭은 import 경계 양쪽을 resolve해 비교한다.
- 의도적인 health 응답 계약 불일치가 실패로 판정되고 해당 Uvicorn 프로세스와 임시 폴더가 정리되는 것을 확인했다. 기존 8000/DB는 사용하지 않았다.
- 기존 TestClient의 Starlette/httpx deprecation 경고는 남아 있다. 현재 실패는 아니며 런타임/의존성 후속 갱신 때 별도 검토한다.
