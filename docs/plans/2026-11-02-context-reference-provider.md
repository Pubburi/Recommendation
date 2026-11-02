# R07 명시 다중 상품 맥락의 추천 제공자

기준 main `d0e333a`에서 기존 제공자는 단일 기준의 similar까지 지원한다. 최신 필수 R07에는
장바구니·데모 주문의 명시 상품 맥락이 필요하므로 별도 opt-in `/v1/recommendations/context`를
구현한다. 기존 API의 결함이나 과거 공동구매 모델 장애로 표현하지 않는다. Backend의 장바구니/
주문·권한·웹 연동과 전체 R07은 미완료다. 원천 수집·업무 DB/공유 포트 변경은 필요하지 않다.

## 구현 전 고정과 기준선

구현 전2026-11-02 14:41:47.035855Z에 직접 작성한13상품·시연 가격/검수 그룹과4기준(available2·unavailable1·
missing1), hard 조건/제외·limit을 동결했다. spec SHA256:
`7aaaf1e3e947c94d70e4467bf62ec9a968b8467436dbee0bb06604456f8042d2`.
원본과 실제 응답/로그는 ignored에만 보존한다. 명시 사실상 반환 가능한 상품은20/40, 각 winning
기준은10/30, 알려진 기준 그룹 제거6개·hard 적격2개다. unavailable60의 같은 그룹 변형61도
후보에서 제외한다. unknown 가격/도수·상한 초과·명시 제외는 재노출하면 안 된다.

소유한 동적 loopback Uvicorn에서 새 path의404와 기존 health/B0/content/similar/exploration의
200/전체 응답을 실제 기록하고 프로세스를 종료했다. 초기 명세의 `[20,40]` 순서는 '둘 다 같은
사실이면 정확히 동점'이라고 가정한 오류였다. 기존 B1은20에0.9999999999999999,40에1.0을
주므로 원점수 정렬은 `[40,20]`이다. 원본 고정 명세를 덮어쓰지 않고 보정 기록을 남겼으며 독립
사실 기대는 후보 집합/기준 사실로 한정했다. 기존 점수를 반올림하거나 기대에 맞춰 바꾸지 않았다.
정확한 tie 정책은 별도1토큰 허구 조건으로 검증한다. 이 관측은 모델 품질 정답이 아니다.

## 계약 선택과 구현

- 기준1–20개는 현재 catalog의 명시 정수 ID다. 중복/잘못된 타입은 거절하고 없는 ID는 missing,
  판매 불가는 unavailable로 남긴다. available만 비교하되 모든 **알려진** 기준의 상품군을 제거한다.
- 전체 요청 catalog에 기존 B1을1회 fit하고 기존 `similar`를 기준마다 재사용한다. 후보의 최종
  점수는 기준별 양수 점수의 max이며 동률은 작은 기준 ID다. winning 항목의 기여·이유·점수와
  별도 matches의 기준 ID를 보존한다. 합산·주문 수량 가중·도수/용량 평균 추정은 하지 않는다.
- max는 어느 한 기준과의 사실 유사도다. centroid/평균은 서로 다른 주종·용량을 가공한 중심을
  만들고 개별 기준의 원래 기여를 그대로 제시하기 어렵다. min/전체 평균은 '모든 상품과 적합'
  이라는 별도 정책이므로 이번 초기 제공자에는 채택하지 않는다. 사람 품질 비교는 수행하지 않았다.
- 각 기준의 topK 합집합이면 max의 전체 topK를 보존할 수 있어 기존 ranker에 요청 limit만
  전달한다. max 외의 새 점수/텍스트 모델을 만들지 않는다. hard·양수/floor·scarcity는 유지한다.
- usable 기준이 없으면 import/fit과 후보 평가를 건너뛰고 empty/null을 반환한다. 일부 기준만
  유효하면 per-reference 상태·미평가 null과 실제 available 기준 진단을 구분한다. 무정보/무공유/
  후보 없음·floor 미달도 빈 fallback으로 남긴다. 자세한 필드는 [CONTEXT-API](../CONTEXT-API.md)다.
- 기존 raw cap/deadline·중복 JSON/문법 오류 우선순위를 새 path에도 적용하며 startup/health/B0의
  수치 런타임 독립과 요청 간 상태 격리를 보존한다. 수신 timeout은 CPU 계산 취소 보장이 아니다.

## 실제 실행과 검증

동결한 같은13상품의 실제 새 HTTP는200·원래 B1 점수순 `[40,20]`/winning30·10이었다. hard 적격2·
기준 그룹 제거6과 unavailable/missing 상태를 확인했다. 기존 다섯 경로의 **전체 응답이 구현 전과
같았고** 새 응답 반복도 전체 동일했다. 소유 baseline/after 프로세스는 모두 종료했다. 이는 허구
사실의 새 정책 계약이며 서비스 오류율 감소·추천 품질·구매 통계·성능 개선 수치가 아니다.

Python3.12.14·고정 uv0.13.6으로 `./scripts/check.sh` 전체가 성공했다. 저장소 생성물/비밀정보
검사·locked sync·Ruff/format·pytest728개(새35개), 기존 B0/content 고정 시나리오 각8/8,
새 sdist/wheel·잠금 runtime-only 격리 설치가 통과했다. checkout 밖 `python -I`의
startup/OpenAPI/usable 기준 없음에서 NumPy/sklearn 미로드를 확인했고, 실제 health/B0/B1/
exploration/similar/context HTTP·winning 기존 similar 항목 전체 비교·순열/부분 기준/입력 거절·
production10초 부분 본문408을 확인했다. 기존 TestClient deprecation 경고1개가 남는다.
테스트 수/CI 시간은 앱 성능이나 추천 품질 수치가 아니다. 로그·모델 응답·실험 명세는 ignored에만
보관한다. README의 세 사례 구간은 구현 전과 byte 동일했다.

최신 head의 필수 CI/완료 Codex·미해결0·Squash/main CI·ff-only와 병합 브랜치 정리는 조정자의
별도 최종 게이트다. 이번 기록은 구현/로컬 검증 완료이며 아직 병합 완료로 표시하지 않는다.

## 데이터 상태와 README 비교

새 source GET·실서비스 SKU/업무 mapping·실서비스 카탈로그 fit은0이다. 이번 허구 request-local
fit을 기존 실제 source-backed 업무 DEMO1상품·실제11상품군/2제조사5fit6transform·6상품군/
11문맥과 합산하지 않는다. 사용자·미래 로그나 평가자 모집을 선행 조건으로 두지 않는다.

현재 README의 세 사례는 원천 완료 상태(CS05), HTTP JSON 의미(CS06), 원천 수량→실제 fit
정합성(CS07)의 관측한 결함과 원인/수정 근거다. 이번은 새 mandatory 제공자의 설계/동작이며
더 강한 독립 실제 문제 해결의 근거는 아직 없어 세 본문·순서를 그대로 보존하고 기능 표만
갱신한다. 대표3/4·부족1을 유지하며 R07/Backend·웹 연결·다중 서비스 SKU/독립 사실 평가를
실행한 뒤 다시 판단한다. 신규 기능/테스트 수만으로 네 번째 사례를 만들지 않는다.
