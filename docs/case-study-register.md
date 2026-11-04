# Recommendation 문제 해결 사례

현재 README의 독립적인 실제 사례는 **3개**, 목표4개까지 **부족1개**다. 문제의 영향·원인
증거·대안·구현과 재현 결과를 기준으로 더 강한 독립 사례가 있을 때만 교체한다. 새 기능/모델 이름,
코드 크기·검사 수·CI 집계로 사례를 나누거나 수를 채우지 않는다.

| ID | 현재 사례 | 구체 근거 |
|---|---|---|
| REC-CS05 | HTTP200의 원천 오류와 수집 완료/상품 부재 분리 | [수집 코드](../src/pubburi_recommendation/wikidata_collect.py)·[당시 오류/회귀 기록](https://github.com/Pubburi/Recommendation/blob/39647aab11e2bb212a23162ad1c57596860b32a7/docs/plans/2026-11-01-wikidata-collection.md) |
| REC-CS06 | 중복 JSON의 마지막 값 선택을 거절해 필수 조건/상품 ID 보존 | [동일 HTTP 입력의 전후 원값](measurements/2026-11-02-ambiguous-json.md) |
| REC-CS07 | 수량 단위/타입 모순을 실제 학습 관측 전에 보류 | [동결 손상·실자료 재현](measurements/2026-11-02-source-quantity-fit-integrity.md)·[기계 판독 원값](measurements/2026-11-02-source-quantity-fit-integrity.json) |

상품군/포장/DEMO mapping·B1 fit·cohort/M1 비교와 새 provider는 각각의 검증 범위가 있다.
현재 세 사례보다 강한 독립 서비스 영향·원인 해결의 근거가 없어 별도 사례로 세지 않는다.
최근 family1 적용도 [기존 계약의 안전 집계](FAMILY-BROWSE-DEMO.md#실행된-데이터-범위)로
통합했고 반복 비교 일지를 남기지 않는다. README 세 본문·순서와 구체 근거 링크는 유지한다.

부족한1개는 실제 필수 연동/장애·fallback 등 독립 문제를 해결하고 전후 원값·원인·대안·구현을
확보한 뒤 판단한다. 신규 사용자/미래 로그를 기다리거나 서비스 품질/성과를 꾸미지 않는다.
MVP 필수 구현·연결/인수가 우선이며 포트폴리오용 과제를 만들지 않는다. 추가 사례 확보와
선택 최적화는 MVP 인수 뒤2027-01-01부터다.

성능 주장은 동일 조건의 실제 before/after 측정이 필요하다. correctness 검사·감사 건수 감소나
CI 시간은 앱 성능이 아니다. 매 실행마다 이 문서를 갱신하지 않고 선정 상태/근거가 달라질 때만
수정하며 구현/검증의 상세 이력은 Git/PR/CI에 둔다.
