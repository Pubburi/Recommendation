# 저장 취향을 기존 B1 입력으로 연결하기

기존 `POST /v1/recommendations/content`, `/exploration`, `/feedback`은 선택적 `preferences`로
Backend GET 취향의 완전한 shape를 받는다. 기존 R06의 `SearchPreferenceSnapshot` DTO를
그대로 재사용한다. 새 endpoint·모델·계정/DB 조회는 없으며 생략 시 기존 입력/응답을 유지한다.
`content`는 검수 DEMO에서 Backend의 본인 권한·현재 취향/업무 재확인과 React 홈의 명시
추천·R04 이유 요청에 연결했다. `exploration`/`feedback` 소비와 일반 서비스 인수는 후속이다.

~~~json
{
  "catalog": [{"product_id": 1, "available": true, "sku_group": "authored-demo", "category": "맥주", "price_krw": 0, "abv_percent": 0}],
  "preferences": {
    "surveyStatus": "COMPLETED",
    "softPreferences": {"categories": ["맥주"], "tasteTags": null, "aromaTags": [], "targetAbvPercent": 0},
    "hardConstraints": {"minPriceKrw": null, "maxPriceKrw": 1000, "minAbvPercent": null, "maxAbvPercent": 10}
  },
  "constraints": {"max_price_krw": 500, "exclude_product_ids": []},
  "include_explanations": true
}
~~~

위 상품/가격은 직접 작성한 문법 예다. `preferences` 자체의 null·일부 필드 생략·추가 필드나
명시 `profile`과의 동시 입력(빈 `{}` 포함)은422다. surveyStatus/softPreferences/hardConstraints와
각 내부 필드를 모두 보낸다. 저장 취향을 쓰지 않을 때는 `preferences` key를 생략한다.

## 변환과 조건

| Backend 입력 | 기존 B1 의미 |
|---|---|
| softPreferences.categories | profile.categories. soft로 유지하며 hard 주종으로 승격하지 않음 |
| tasteTags / aromaTags | 각각 profile.taste_tags / aroma_tags. literal atom을 보존 |
| targetAbvPercent | preferred_abv_percent. 실제0을 유지하며 soft target이 hard 범위 밖이어도 hard를 바꾸지 않음 |
| min/maxPriceKrw | 기존 가격 hard bounds와 교집합 |
| min/maxAbvPercent | 기존 도수 hard bounds와 교집합 |
| surveyStatus NOT_STARTED / SKIPPED | 모든 취향 필드는 null이어야 함. 별도 활동 주종이 없으면 기존 빈 취향/B0 fallback 유지 |

완료 설문의 null은 미확인, `[]`는 확인한 선택 없음이다. 요청 snapshot은 둘을 그대로 보존하고
둘 다 긍정 취향 근거를 제공하지 않는다. 입력을 수정하거나 저장하지 않는다. 가격/도수의0은
null로 바꾸지 않는다. volume 취향을 추정하거나 R06의 검색 opt-in을 추천 hard로 바꾸지 않는다.

각 hard 하한은 더 큰 값, 상한은 더 작은 값을 사용한다. 한쪽 null은 그쪽 제한이 없다는 뜻이다.
교집합 하한>상한이면 fit 전에422 `preferences_and_request_hard_bounds_conflict`로 거절한다.
기존 추가 constraints의 hard 주종/제외 ID와 feedback의 negative/positive 그룹 정책은 그대로다.
결과가 비어도 조건을 넓히지 않는다. 원래 모델 원점수·순서·기여·이유/승리 기준과 요청별1fit,
정보 없는 profile fallback/positive mode의 무채움을 재사용한다. 빈 catalog는 fit하지 않는다.

## 활동 주종 입력

`content`와 `feedback`에서 선택적 `activity_categories`를 받는다. Backend가 현재 본인과 권한 상태를
확인하고 승인된 현재 가용 상품의 찜과 상품별 최신 본인 후기(4점 이상)를 각각 주종 배열로 전달한다.
필수 두 키는 `favorite_categories`, `highly_rated_categories`이며 각각 기존 8개 주종의 고유 배열이다.
두 배열이 공유하는 주종은 한 번만 반영한다. 합집합은 비어 있으면 안 되며 모든 주종이
`catalog`의 `available: true` 상품에 있어야 한다.

완전한 `preferences`와 `softPreferences.categories: null`이 필요하다. 명시 선택(`[]` 포함),
별도 `profile`, 추가 키 또는 활동 입력 자체가 null이면 422다. 활동이 없으면 키를 생략한다.
유효한 세 설문 상태 모두 원본 snapshot을 유지하며 합집합은 요청의 B1 soft 주종만 채운다.
맛·향·도수 취향과 필수/제외 조건은 기존 변환을 따른다. 응답의 점수·이유는 기존 B1 의미를
유지한다. 계정·찜 상품 ID·평점·원시 활동은 전달하지 않으며 제공자 응답에 활동 필드를 추가하지 않는다.

## 정확한 원문과 정규화 경계

기존 [R06 입력 계약](SEARCH-PHRASES-API.md)의8개 주종·각20태그/40 UTF-16단위·엄격 타입/
완전한 상태와 필드 규칙을 따른다. Backend가 Java17 규칙으로 정규화한 GET 값을 전달한다.
Recommendation은 Java의 전체 Unicode 정규화와 Python 규칙이 같다고 확인하지 않는다.
기존 B1 `ContentProfile`로 바꿨을 때 원문 tag가 하나라도 변하면
422 `preferences_require_lossless_b1_tag_literals`로 거절한다. 공백·대소문자를 몰래 바꾸거나
해당 필드를 버려 요청을 약화하지 않는다. 쉼표/개행은 한 atom 안에서 그대로 유지한다.
Backend의 최종 canonical 검증·계정 권한·저장 상태에 대한 책임은 계속 Backend에 있다.

새 필드가 있는 세 경로는 bounded 원문을 Decimal로 다시 검증해 Backend의0–100/소수점2자리
계약을 지킨다. `13.750`·`0.000`을 binary float가 지운 뒤 승인하지 않는다. 원문 Decimal 변환
예외는 고정422로 처리한다. 새 필드가 없는 기존 profile/catalog/constraints의 수치 계약과
R06의 원문·오류 우선순위는 그대로다. 파싱 후 engine은 기존 thread pool 경로에서 실행한다.
전체512KiB/10초 수신 제한·중복 key와 malformed 우선·비반사 오류를 유지한다.

이 입력 연결은 현재 권리 검수·명시 catalog/business mapping을 대신하지 않는다. 임의 동의 flag나
저장 취향이 source11·업무 DEMO1·별도 browse DEMO5/legacy80을 서비스 SKU/품질로 승격하지 않는다.
`content`의 검수 DEMO 연결과 별개로 `exploration`/`feedback`의 업무/웹 소비·서비스 카탈로그
채택과 전체 R02/R05/R08/AI02 인수는 미완료다.

[동결/실행 계획](https://github.com/Pubburi/Recommendation/blob/39647aab11e2bb212a23162ad1c57596860b32a7/docs/plans/2026-11-04-backend-preference-input.md) · [검증](TESTING.md)
