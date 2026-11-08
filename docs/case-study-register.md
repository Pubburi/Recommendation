# Recommendation 문제 해결 사례

현재 README의 독립적인 실제 사례는 **4개**다. 문제의 영향·원인
증거·대안·구현과 재현 결과를 기준으로 더 강한 독립 사례가 있을 때만 교체한다. 새 기능/모델 이름,
코드 크기·검사 수·CI 집계로 사례를 나누거나 수를 채우지 않는다.

| ID | 현재 사례 | 구체 근거 |
|---|---|---|
| REC-CS05 | HTTP200의 원천 오류와 수집 완료/상품 부재 분리 | [수집 코드](../src/pubburi_recommendation/wikidata_collect.py)·[당시 오류/회귀 기록](https://github.com/Pubburi/Recommendation/blob/39647aab11e2bb212a23162ad1c57596860b32a7/docs/plans/2026-11-01-wikidata-collection.md) |
| REC-CS06 | 중복 JSON의 마지막 값 선택을 거절해 필수 조건/상품 ID 보존 | [동일 HTTP 입력의 전후 원값](measurements/2026-11-02-ambiguous-json.md) |
| REC-CS07 | 수량 단위/타입 모순을 실제 학습 관측 전에 보류 | [동결 손상·실자료 재현](measurements/2026-11-02-source-quantity-fit-integrity.md)·[기계 판독 원값](measurements/2026-11-02-source-quantity-fit-integrity.json) |
| REC-CS08 | health 뒤 첫 B1의 요청 예산 초과를 lifespan 준비 경계로 이동 | [동일 설치/입력의 원값과 startup 비용](measurements/2026-11-08-b1-startup-boundary.md)·[측정값](measurements/2026-11-08-b1-startup-boundary.json)·[실제 lifespan](../src/pubburi_recommendation/main.py) |

상품군/포장/DEMO mapping·B1 fit·cohort/M1 비교와 새 provider는 각각의 검증 범위가 있다.
그 구현 수로 사례를 나누지 않는다. REC-CS08은 로컬 운영 통합에서 실제 대체 응답을 유발한
첫 요청 경계를 별도로 재현했고, 같은 runtime-only 새 설치3회와 동일 카탈로그의 원값·
같은 프로세스 warm/재시작·startup 비용·응답 보존을 분리했다. 기존 세 사례의 원천 수집/
JSON/단위 정합성과 다른 프로세스 준비/요청 deadline 문제여서 부족했던 네 번째로 채택했다.
기존 세 본문과 순서는 보존한다. 요청 시간 감소율·검사 수나 초기화 총시간 개선을 성과로 삼지 않는다.

성능 주장은 동일 조건의 실제 before/after 측정이 필요하다. correctness 검사·감사 건수 감소나
CI 시간은 앱 성능이 아니다. 매 실행마다 이 문서를 갱신하지 않고 선정 상태/근거가 달라질 때만
수정하며 구현/검증의 상세 이력은 Git/PR/CI에 둔다.
