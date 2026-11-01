# AI02/04 — 추천 입력 JSON 의미 보존

- 기준 main `bcb1b1d`, `codex/reject-ambiguous-catalog-json`. Recommendation만 작성한다.
  root가 PR/최신 CI·Codex/병합/main CI·브랜치·lease·기획을 소유한다. PostgreSQL18.6/JPA/
  Flyway·Psycopg3 전환을 기다리거나 업무 DB 직접 접근을 추가하지 않았다.
- 실제 기존 HTTP의 중복 도수 상한/상품 ID가 마지막 값으로 덮이는 결함을 자체 허구 입력으로
  재현했다. 수정 전 두 경계 회귀를 먼저 실패시켰다. 현재 모델/카탈로그 품질 실험을 반복하는
  대신 요청 해석→제약/ID 유실의 원인을 수정하는 한 목적의 제품 변경이다.
- 같은 동결 harness/input·Uvicorn/Python에서 직접 HTTP4조건 전후를 비교해 오승인4/4→0/4,
  정상 제약2조건을 유지했다. 첫 sandbox socket bind 거절 뒤 허용된 독립 동적 port로
  실행했으며 각 자식 PID를 종료/회수했다. 공유 DB·8000·성능 자원을 사용하지 않았다.
- 기존512KiB/10초 수신을 먼저 검사한 뒤 JSON media 요청의 object별 decoded key 중복을
  고정422로 거절한다. 동일 값/escape도 중복으로 처리하고 다른 객체의 같은 이름은 허용한다.
  첫/마지막 값을 정답으로 고르지 않으며 조건·상품 데이터 원문/개인 key를 반사하지 않는다.
- decoder 추가 pass 비용이 있고 이를 속도 개선·전체 CPU timeout으로 표현하지 않는다.
  syntax/encoding/depth·RecursionError는 기존4xx 처리에 맡기며 typed schema/numeric·정상
  B0/B1/health/OpenAPI/수치 런타임 lazy import를 유지한다. 원천/모델/서비스 신규 매핑은 그대로다.
- README REC-CS02의 예방 설계는 보관하고 실제 원인/재현·수정·대안/비용이 있는 새 사례로
  교체한다. 원천 수집 사례/순서와 대표2/4는 유지한다. 회귀 수/목록·CI 집계는 README에 넣지
  않고 이 계획과 PR에 남긴다. 강한 실문제 근거를 기준으로 교체했으며 세 번째로 나누지 않았다.

최종 검증/인계는 아래에 기록한다. [전후 조건/원값](../measurements/2026-11-02-ambiguous-json.md).

- 수정 전 새 경계 회귀의 두422 기대가 실제200으로 실패했다. 수정 후 새24개와 기존B0/B1의
  focused100개가 통과했다. 전체 `./scripts/check.sh`도 Python3.12.14에서 안전 검사·locked
  의존성·Ruff/format·pytest488개·기존 authored 평가와 새 sdist/wheel을 통과했다. 별도 설치의
  runtime-only `python -I` CLI와 실제 health/B0/B1/OpenAPI·중복hard/ID 원문4조건·프로덕션
  10초 부분본문408도 확인했다. 기존 Starlette TestClient deprecation 경고1개는 남는다.
- 최초 전체 검사에서 README 코드 발췌 끝의 빈 줄 포맷이 실패해 이를 정리한 뒤 전체를 다시
  통과했다. 필수 검사를 생략/완화하거나 실패를 성공으로 기록하지 않았다.
- PR 생성·최신 head 필수CI/완료Codex·구체 미해결 지적·병합/main CI와 브랜치 정리는 조정자
  인계 후 처리하며 로컬 성공을 병합/PG 전환 완료로 표시하지 않는다.

## PR21 오류 우선순위 리뷰 수정

- [정식 지적](https://github.com/Pubburi/Recommendation/pull/21#discussion_r4436350617)은 hook의
  즉시 예외가 중복 객체 뒤의 잘린 값/trailing 문법 오류를 `duplicate_json_key`로 덮는 경계였다.
  일반 FastAPI 대조 앱은 같은 원문을 `json_invalid`로 거절하지만 이전 head는 중복 오류로
  바뀌는 것을 두 endpoint 회귀에서 먼저 실패 재현했다.
- hook은 요청별 중복 flag만 남기고 전체 `json.loads` 성공 뒤에만 flag를 반환한다. syntax/
  encoding/depth 오류는 False로 기존 framework에 위임하며 불필요한 예외 클래스를 제거했다.
  정상 JSON의 중복 거절·고정 진단·object/media/escaped 이름·기동 경계는 유지한다.
- nested/root·truncated/trailing·escaped 중복과 parser 깊이 오류를 양쪽 endpoint에서 일반
  framework의 응답 type/loc/msg/상태와 직접 비교한다. 이 runtime에서2000중첩은 실제 decode가
  성공하므로 깊이 오류 재현에는 실제 RecursionError가 난10000중첩(본문 상한 내)을 사용했다.
  새12조건과 기존100개를 합한 focused112개를 통과했다.
- README 실제 helper 발췌와 API/운영 문서를 같은 flag/전체 문법 검증 순서로 맞췄다. 기존
  동결4조건은 유효한 JSON의 중복 재현이므로 그 전후 결과/분모를 보존한다. 새 문법 우선순위
  회귀를 오승인4조건의 분모에 합산하지 않는다. 답글/native 해결은 조정자만 처리한다.
- 최신 수정의 `./scripts/check.sh`는 Python3.12.14·Ruff/format·pytest500개·새 sdist/wheel의
  runtime-only CLI·실제 HTTP 유효중복4조건과 별도 문법우선4조건·health/B0/B1/OpenAPI·
  프로덕션10초408을 모두 통과했다. 기존 TestClient 경고1개는 남는다. 이전488개 결과와 최신
  500개 결과의 source head를 구분하고 최신 CI/완료 리뷰·native 해결은 조정자에게 재인계한다.
