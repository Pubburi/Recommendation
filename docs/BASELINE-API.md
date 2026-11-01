# B0 추천 API v1

`POST /v1/recommendations/baseline`은 Backend가 제공한 명시 카탈로그에 필수·제외 조건을
적용하고 상품 ID 오름차순으로 반환한다. 학습하지 않은 **B0 기준선**이며 개인 취향 점수·인기
통계를 제공하지 않는다. `GET /health` 계약은 유지한다. OpenAPI 정본은 실행 서버의
`/openapi.json`이며 이 문서는 호출 책임과 필드 의미를 설명한다.

## 경계와 책임

- 추천 서버는 입력을 저장하지 않고 DB·모델 파일·외부 API·개인 식별정보 없이 계산한다.
- Backend는 사용자/권한, 취향·관심 없음 저장, 상품 원본·최신 가격/판매 상태와 공개 API의
  `ApiResponse`를 소유한다. 이 내부 API의 원시 JSON과 Backend `/api` 규격은 별개다.
- `available`은 Backend가 확인해 전달해야 한다. 응답 ID를 고객에 노출하기 전에도 최신 상품과
  명시 조건을 재검증한다. 이 API에 클라이언트 입력 가격/상태를 그대로 중계하지 않는다.
- 현재 기본 목록 호출의 범위는 아래 계약에 한정하며 인증·명시 취향/B1·웹 사용자 흐름 완료를
  뜻하지 않는다. 로컬 서비스용 계약이며 외부 공개 배포의 인증·접근 통제 완료로 간주하지 않는다.
- B1 특성/TF-IDF fit·데이터 권리/품질 감사·관련성 평가와 R01–R08 사용자 흐름 완료는 후속이다.

## 요청

```json
{
  "catalog": [
    {"product_id": 21, "available": true, "category": "fixture-a", "price_krw": 2000, "abv_percent": 5},
    {"product_id": 8, "available": true, "category": "fixture-a", "price_krw": null, "abv_percent": 6},
    {"product_id": 3, "available": false, "category": "fixture-a", "price_krw": 1000, "abv_percent": 5}
  ],
  "constraints": {
    "categories": ["fixture-a"],
    "exclude_product_ids": [],
    "min_price_krw": 0,
    "max_price_krw": 2000,
    "min_abv_percent": null,
    "max_abv_percent": 6
  },
  "limit": 12
}
```

위 값은 문서 설명용으로 직접 작성한 가상 카탈로그다. 실제 주류의 가격·도수·선호를 뜻하지 않는다.

| 필드 | 계약 |
|---|---|
| `catalog` | 필수 배열, 0–1000개. `product_id`가 중복이면 전체 요청을 422로 거절 |
| `product_id` | 1–2,147,483,647의 정수. 숫자 문자열·실수·불리언 허용 안 함 |
| `available` | 필수 JSON boolean. 호출 목적에서 Backend가 확인한 후보 적격성. 공개 목록 노출과 판매·재고 적격성의 범위를 구분하며, 미확인 판매 가능성을 true로 추정하지 않음 |
| `category` | null 또는 1–64자 문자열. 앞뒤 공백 제거 후 비어 있으면 거절. 대소문자를 구분하는 정확 일치 |
| `price_krw` | null 또는 0–2,147,483,647의 정수 원화 금액. 설명용/실제 가격의 성격은 Backend가 관리 |
| `abv_percent` | null 또는 유한한 0–100 수치. NaN/Infinity·숫자 문자열·불리언 거절 |
| `constraints` | 생략 시 명시 필터 없음. 미정의 필드 거절 |
| `categories` | 허용 주종 배열, 최대 32개. 빈 배열은 주종 제한 없음 |
| `exclude_product_ids` | 제외 ID 배열, 최대 1000개. 중복 제외값은 같은 제외로 처리 |
| `min/max_price_krw` | 양 끝 포함, 가격 타입/범위와 동일. null/생략은 해당 방향 제한 없음 |
| `min/max_abv_percent` | 양 끝 포함, 도수 타입/범위와 동일. null/생략은 해당 방향 제한 없음 |
| `limit` | 1–100 정수, 기본 12. 필터·정렬 뒤 적용 |

[Backend 공개 기본 목록](https://github.com/Pubburi/Backend/blob/main/docs/DEFAULT-RECOMMENDATIONS.md)은
판매/재고 필드가 없어 후보 조회 시 현재 상품 행이 존재한다는 범위만 `available=true`로 전달한다.
이 호출의 `available` 이유는 공개 목록 후보 적격성만 뜻하며 판매·재고 확인을 보장하지 않는다.
이를 다른 판매/주문 호출의 미확인 상태를 true로 채우는 일반 규칙으로 사용하지 않는다.

모든 객체는 미정의 필드를 거절한다. min > max는 422다. 카테고리 문자열의 길이와 배열 수 외에
원문 JSON도 **524,288 bytes(512 KiB)**까지 허용하며 초과하면 파싱 전에 413을 반환한다.
같은 JSON 객체의 중복 필드명은 마지막 값을 선택하지 않고422 `duplicate_json_key`로 거절한다.
escape를 푼 이름이 같거나 값이 같아도 거절하며 서로 다른 상품 객체에 같은 필드명이 있는 것은
정상이다. JSON media type(`application/json`, `application/*+json`)과 Content-Type이 없는
JSON 요청에 적용한다. 진단은 고정 type/loc/msg이고 중복 key/값·원문을 반사하지 않는다.
중복은 요청별 flag로만 기록하고 전체 JSON 문법 검증이 성공한 경우에만 이 진단을 반환한다.
중복 객체 뒤에 잘린 값/잘못된 trailing data가 있으면 기존 `json_invalid` 등이 우선한다.
512KiB 수신 후 별도 decoder pass를 수행하는 비용이 있으며 schema/비유한 수치·불완전 JSON/
인코딩·깊이 오류는 기존 framework의4xx 검증 경로를 유지한다. 계산 속도 개선 주장은 없다.
Content-Length가 없거나 여러 ASGI body 조각으로 전송해도 누적 크기를 확인한다.
전체 본문 수신 예산은10초이며 초과하면408 고정 JSON을 반환한다. 조각별로 시간을 갱신하지
않고 본문 수신 중 연결 종료가 확인되면 파싱/계산하지 않는다. 이는 본문 수신 예산이며 계산 시간의 보장은 아니다.

## 조건·이유·후보 부족

1. `available=false`와 제외 ID는 항상 제거한다.
2. 허용 주종이 있으면 해당 주종과 일치해야 한다. 주종 미확인은 통과시키지 않는다.
3. 가격/도수의 한쪽 이상 범위를 지정하면 해당 속성이 반드시 확인돼 있어야 한다.
   null/생략은 unknown이며 0으로 채우지 않는다. 미지정 속성에는 임의 불이익을 주지 않는다.
4. 조건을 통과한 후보를 상품 ID 오름차순으로 정렬한 뒤 limit을 적용한다.
   입력 순서나 전역 상태에 의존하지 않는다. 더 적게 반환되더라도 예산·도수·제외를 완화하지 않는다.

```json
{
  "algorithm": "b0-id-ascending-v1",
  "items": [{
    "product_id": 21,
    "reasons": ["available", "category_match", "price_within_range", "abv_within_range", "deterministic_baseline"]
  }],
  "eligible_count": 1,
  "fallback_reason": null
}
```

`eligible_count`는 limit 적용 전 통과 후보 수다. `reasons`는 실제 적용한 조건 코드이며 취향
일치 확률이나 점수 해석이 아니다. `available`·`deterministic_baseline`은 항상 포함하고,
`category_match`·`price_within_range`·`abv_within_range`는 요청에 해당 필터가 있을 때만 포함한다.
통과 후보가 없으면 `items=[]`, `eligible_count=0`, `fallback_reason="no_eligible_products"`다.
빈 카탈로그도 동일하게 처리한다. Backend의 서비스 장애 fallback과 후보 부족 응답을 혼동하지 않는다.

## 오류·검증

- 422: 타입/범위·상한·중복 ID·역전 범위·미정의 필드 등 계약 위반.
  `detail`에 `type`·`loc`·`msg`를 반환하고 원문 입력값/카탈로그는 되돌려 보내지 않는다.
- 413: 누적 JSON 원문 크기 초과.
- 408: 전체 본문 수신10초 초과. `{"detail":"Catalog request body timed out"}`.
- 계약 확인은 직접 작성한 fixture, 실제 HTTP와 새 wheel의 격리 실행에서 수행한다.
  fixture 통과를 실제 사용자 선호·추천 적중률·CTR 성과로 표현하지 않는다.

공식 구현 근거: [Pydantic 필드 제약](https://docs.pydantic.dev/latest/concepts/fields/),
[모델 검증기](https://docs.pydantic.dev/latest/concepts/validators/),
[FastAPI 응답 모델](https://fastapi.tiangolo.com/tutorial/response-model/).
