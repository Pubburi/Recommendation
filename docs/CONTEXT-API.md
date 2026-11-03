# 명시 상품 맥락 추천 API — R07 추천 제공자

선택적 `include_explanations: true`는 [R04 사실 설명](EXPLANATIONS.md)을 추가한다.
엄격 boolean/기본false이며 생략/false에는 기존 응답을 보존한다. 원점수·순서·fit/정책을
바꾸지 않고 profile/실제 winning 기준 ID의 사실을 구분한다.

`POST /v1/recommendations/context`는 장바구니·데모 주문에서 호출자가 명시한 여러 상품의 사실을
기존 B1으로 비교한다. 각 후보의 **가장 잘 맞는 기준 상품 하나**의 양수 점수와 실제 기여를
반환한다. 전체 장바구니와의 적합성·함께 구매한 통계·사용자 선호를 학습한 점수가 아니다.
R07의 추천 소유 제공자 증분이며 Backend의 장바구니/주문·권한·웹 연결은 미완료다.

## 요청

```json
{
  "catalog": [],
  "reference_product_ids": [1, 2],
  "constraints": {},
  "min_relevance_score": 0.0,
  "limit": 12
}
```

- `catalog`는 기존 [content 계약](CONTENT-API.md)의 최대1000개 검수 상품이다. 빈 목록은
  허용하지만 중복 상품 ID는 거절한다. 이름·원천 entity ID로 업무 ID나 상품군을 추정하지 않는다.
- `reference_product_ids`는 중복 없는1–20개 정수 ID이며 각 값은1–2,147,483,647이다.
  catalog에서 찾지 못한 ID는 `missing`, 판매 불가는 `unavailable`로 명시하고 점수 계산에서
  제외한다. 일부만 유효해도 나머지 상태를 숨기지 않는다. 문자열·boolean·중복/상한 초과는422다.
- `constraints`는 주종·가격/도수·판매 상태·제외 ID의 기존 hard 조건이다. 기준 상품의 주종은
  soft 근거이며 후보의 필수 주종이 되지 않는다. 기준 ID가 hard 제외 목록에 있어도 그 명시
  사실은 맥락에 사용할 수 있다. hard 조건은 반환 후보에 적용한다.
- `min_relevance_score`는 유한한0–1, 기본0이다. 양수이면서 이 값 이상인 후보만 반환한다.
  `limit`은 정수1–100, 기본12다. 부족하면 그대로 적게 반환하며 조건/그룹/floor를 완화하지 않는다.

수량·중복 주문 횟수·사용자 ID·선호 profile은 받지 않는다. 같은 사실을 가진 같은 그룹의 기준을
추가해도 점수를 합산하거나 가중하지 않는다. 같은 그룹의 다른 변형에서 사실이 다르면 각각의
명시 사실과 비교할 수 있으나 그 그룹 전체는 반환 후보에서 제외한다.

## 계산과 근거

1. catalog에서 **찾은 모든 기준**의 `sku_group` 합집합을 후보에서 제거한다. 판매 불가 기준의
   알려진 그룹도 제외한다. missing ID의 그룹은 만들지 않는다. 내부 제거가 호출자의1000개
   제외 ID 예산을 소비하지 않는다.
2. available 기준이 하나도 없으면 수치 런타임 import/fit 없이 빈 `no_usable_references`를
   반환한다. `eligible_count`와 `excluded_reference_group_count`는 미계산 `null`이다.
3. available 기준이 있으면 전체 명시 catalog로 기존 B1을 요청 안에서 **한 번만 fit**한다.
   기존 known-catalog 계약처럼 reference·판매 불가·hard 탈락 상품도 표현 fit에는 포함된다.
   각 available 기준의 주종/태그·관측 도수/용량을 기존 `similar`에 전달한다.
4. 후보별 점수는 기준별 기존 B1 점수의 최댓값이다. 동점이면 작은 기준 ID의 항목을 유지한다.
   원래 `score/reasons/contributions`는 변경하지 않는다. 양수/floor 후보를 점수 내림차순·
   동점 상품 ID순으로 정렬하고 limit을 적용한다. 부동소수점 점수를 임의로 반올림하지 않는다.
5. 기준별 상위K만 합쳐도 max 기준 전체 상위K를 얻는다. 어떤 후보가 그 후보의 최댓값을
   준 기준의 상위K 밖이라면 그 기준에서 이미 K개 후보가 같은 점수/ID 순서로 앞서기 때문이다.
   이 성질로 반환 limit까지만 기존 엔진에서 받으며 별도 ranker를 만들지 않는다.

unknown은0·새 스타일·미확인 취향 근거가 아니다. 기존 B1의 상수/결측 수치 비활성과 실제 기여
분모를 보존한다. 점수가 높아도 다른 기준 상품과는 맞지 않을 수 있으므로 '전체 장바구니에 잘
어울림'이나 상호 보완 조합이라고 표시하면 안 된다. max는 명시한 초기 정책이며 최적화한
사용자 품질·음식/주류 조합 규칙이 아니다. R08의 MMR·그룹당1개 정책도 여기에 자동 적용하지 않는다.

## 응답과 fallback

| 필드 | 의미 |
|---|---|
| algorithm / aggregation_algorithm | 기존 `b1-tfidf-minmax-v1` / `r07-max-reference-v1` |
| fit_scope / profile_source | `request_catalog` / `explicit_context_product_facts` |
| reference_group_policy | `exclude_all_known_reference_groups` |
| representation_fitted / model_fingerprint | 실제 usable 어휘/수치 표현 여부와 지문. 무정보면 false/null |
| references | 기준 ID순으로 product_id/sku_group/state와 **각 기준**의 지원 토큰·활성 수치/fallback |
| evaluated_reference_count | 실제 비교한 available 기준 수. usable 기준이 없으면0 |
| eligible_count | 기준 그룹 제거와 hard 조건 뒤, 양수/floor/limit 전 적격 수. 미계산은 null |
| excluded_reference_group_count | 모든 알려진 기준 그룹 때문에 제거한 catalog 항목 수. 본인/판매 불가 포함. 미계산은 null |
| items | winning 기준의 기존 B1 항목 전체. 양수/floor를 만족하며 기여 합이 점수 |
| matches | items와 같은 순서의 product_id/reference_product_id. 어느 기준 사실의 기여인지 명시 |

missing/unavailable 기준의 지원 토큰·활성 수치는0/빈 목록이 아닌 `null`로 남긴다. available
기준의 진단은 floor 전에 기존 B1이 계산한 값이며 사용자 취향 지원률이 아니다.

| fallback_reason | 조건 |
|---|---|
| no_usable_references | available 기준 없음. fit/후보 조건 미계산 |
| no_eligible_products | 기준 그룹과 hard 조건 뒤 후보 없음 |
| no_supported_preferences | 적격 후보는 있지만 모든 available 기준에 지원 표현 없음 |
| no_matching_features | 지원 표현이 있지만 모든 기준에서 양수 후보 없음 |
| below_relevance_floor | 양수 후보는 있지만 모두 명시 floor 미달 |
| null | 양수/floor 후보를 반환함 |

## HTTP와 소유권

다른 추천 POST와 같은512KiB 누적 원문·전체10초 수신 기한·object별 JSON 중복 key 고정422와
기존 malformed/인코딩/media별 오류 우선순위를 적용한다. 수신 기한은 CPU fit/20회 이하 기준
비교를 취소하거나 완료 시간을 보장하지 않는다. 요청 간 모델/기준·사용자 상태를 저장하지 않는다.
시작/OpenAPI/health/B0와 usable 기준이 없는 context는 NumPy/sklearn·DB·모델 다운로드·외부
키를 요구하지 않는다. 경계/배포 검증은 [작업 기록](plans/2026-11-02-context-reference-provider.md)을 따른다.

호출자는 허용 사실·업무 ID/검수 그룹·현재 장바구니/주문 권한을 보장한다. Backend는 반환 뒤
현재 상품/판매/가격·제외 조건과 링크를 재확인해야 한다. 이 제공자는 새로운 서비스 카탈로그
매핑·실제 구매 통계·추천 품질/일반화·전체 R07 완료를 승인하지 않는다.
