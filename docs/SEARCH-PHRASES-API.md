# R06 명시 취향의 검색 문구·정확한 조건 제공자

`POST /v1/recommendations/search-phrases`는 고정된 짧은 문구와 **선택하면 적용할 정확한
검색조건**을 함께 반환한다. 상품을 검색/평가하거나 저장하지 않고, catalog·DB·계정 ID·외부
API·LLM·벡터·모델 fit을 요구하지 않는다. 기존6개 추천 POST와 B1 점수/정책은 유지한다.
R06 제공자 증가분이며 Backend/React의 본인 취향 전달·문구 선택·실제 검색/빈 결과 연결은 후속이다.

## 요청 — 이미 정규화한 본인 취향 값과 별도 검색 선택

`preferences`는 Backend `GET /api/users/me/preferences`의 `data`와 같은 shape다.
세 그룹과 아래 nullable 필드가 모두 필수이며 생략/잘못된 타입·미정의 필드는422다.
Backend가 본인 권한/현재 값을 확인해 전달해야 하며 제공자는 출처나 계정 소유권을 검증하지 않는다.

~~~json
{
  "preferences": {
    "surveyStatus": "COMPLETED",
    "softPreferences": {
      "categories": ["맥주"],
      "tasteTags": ["직접 작성한 태그"],
      "aromaTags": null,
      "targetAbvPercent": 0
    },
    "hardConstraints": {
      "minPriceKrw": 0,
      "maxPriceKrw": 20000,
      "minAbvPercent": 0,
      "maxAbvPercent": 10
    }
  },
  "search_opt_in_fields": ["categories", "tasteTags", "targetAbvPercent"],
  "limit": 5
}
~~~

위 값은 실제 상품/사용자 관측이 아닌 문법 설명용이다.

| 필드 | 의미·검증 |
|---|---|
| surveyStatus | NOT_STARTED / SKIPPED / COMPLETED. 앞의 두 상태는 모든 soft/hard 값이 null이어야 함. []와0은 null이 아님 |
| softPreferences.categories | null 또는 최대8개 고유한 기존 정확 라벨: 탁주·약 · 청주·과실주·증류주·위스키·양주·맥주·사케 |
| tasteTags / aromaTags | 각각 null 또는 최대20개·각1–40 UTF-16 단위의 원문 atom. null=unknown, []=명시한 선호 없음 |
| targetAbvPercent | null 또는 JSON 수치0–100·원문 Decimal scale≤2. soft 목표이며 hard 상한이 아님 |
| hardConstraints.min/maxPriceKrw | null 또는 엄격 JSON 정수0–2,147,483,647·하한≤상한. 실제0 보존 |
| hardConstraints.min/maxAbvPercent | null 또는 JSON 수치0–100·원문 scale≤2·하한≤상한 |
| search_opt_in_fields | 기본[]·중복 없는 categories/tasteTags/aromaTags/targetAbvPercent 중 최대4개. 검색에 필수조건으로 쓰기로 별도로 명시 선택한 필드 |
| limit | 기본5·엄격 정수1–5. 상품 수가 아닌 표시 문구 수 |

soft 입력만으로 필터를 만들지 않는다. 호출자는 원래 추천 선호와 **검색에 쓰기로 한 별도 선택**을
구분해야 한다. opt-in은 권리/계정 승인이 아니다. 문자열 숫자·boolean 수치·추정 '저도/달콤'
임계값·동의어·알 수 없는 주종/필드·원문 반올림은 허용하지 않는다.

ABV는 새 경로에만 bounded/cached JSON 원문을 Decimal로 다시 읽어 scale을 검증한다.
13.755·13.750·float 변환으로 자릿수가 사라지는0.10000000000000000000001도422다.
13.70은 정확한 `13.70` ASCII query 값으로 남고 signed -0.00은 실제0.00으로 보존한다.
이는 기존 B1 수치 입력의 정밀도나 다른 경로의 JSON 파서를 바꾼 것이 아니다.
기본 float 파서가0.0으로 읽는 `0e9999999999999999999` 같은 원문의 Decimal 생성 실패도
새 경로의 고정422 `decimal_parsing`으로 반환한다. 예외는 원문 Decimal 재파싱에만 적용하며
진단에 숫자/본문을 넣지 않고 기존 중복 key·malformed 우선순위나 다른 오류를 덮지 않는다.

## 선택·조건·고정 문구

1. 모든 문구에 원래 hard 가격/도수 범위를 공통 적용한다. unknown을0으로 채우거나 범위를
   완화하지 않는다. 선택하지 않은 soft는 query에 넣지 않고 `soft_not_selected`로 구분한다.
2. 선택한 facet은 **하나의 조건에 AND**로 묶는다. 맛/향 각각의 모든 태그도 AND다. 주종만
   Backend의 단일 정확 `type`에 맞춰 각 라벨별 별도 문구로 나눈다. OR·조합 점수/인기도는 없다.
3. targetAbvPercent를 별도로 선택했으면 hard 안에 있을 때만 min=max exact 검색을 제안한다.
   hard 밖이면 빈 items와 conflict다. 목표를 임의 범위·근접 허용으로 바꾸거나 hard를 넓히지 않는다.
4. 선택한 값이 null/[]이면 빈 items와 unknown/empty 진단이다. 해당 facet을 몰래 빼거나
   약한 기본 문구로 채우지 않는다. 여러 진단을 남기며 unknown이 empty보다 fallback 우선이다.
5. 선택이 없으면 hard만 적용한 `지정 조건으로 상품 보기`, hard도 없으면 `전체 상품 보기`
   한 문구다. 선택된 경우에는 `선택한 취향 조건으로 검색` 또는 기존8개 라벨의
   `맥주 조건으로 검색` 같은 고정 enum을 쓴다. 긴 원문 atom을 label에 잘라 넣지 않는다.
6. category와 태그를 결정적으로 정렬한다. 주종 분기는 최대8개이며 limit 밖 후보 수를 밝힌다.
   후보 수는 템플릿 수이고 실제 검색 결과 수가 아니다. 입력 순서·요청 간 상태/모델에 의존하지 않는다.

## 응답과 Backend 매핑

실행 `/openapi.json`의 SearchPhraseRequest/Response·SearchConditions·SearchQueryPair가 공식 schema다.

| 필드 | 의미 |
|---|---|
| algorithm | r06-explicit-search-phrases-v1 |
| items | 최대5개의 template_id·고정 label·conditions·ordered query_pairs·Unicode 재검증 표시 |
| template_id | all_products / hard_conditions / selected_preferences |
| conditions | type·nullable 가격 정수/도수 ASCII 문자열·tasteTag/aromaTag 원문 배열 |
| query_pairs | 각 name/value 쌍. type → min/maxPriceKrw → min/maxAbvPercent → 반복 tasteTag → 반복 aromaTag 순서, 최대45쌍 |
| candidate_count / omitted_count | limit 전 템플릿 후보 수0–8 / limit 때문에 생략한 수0–7 |
| product_count | 항상 null. 상품 검색을 실행하지 않아 미계산이며0으로 쓰지 않음 |
| diagnostics | 각 필드의 soft_not_selected / selected_unknown / selected_empty / backend_unicode_revalidation_required |
| fallback_reason | no_explicit_search_conditions / no_search_opt_in / selected_preferences_unknown / selected_preferences_empty / selected_target_outside_hard_bounds 또는 null |

매핑 대상은 Backend `GET /api/products`다. type은 정확 일치, 가격은 KRW 정수·도수는 vol%
ASCII 소수로 전달한다. tasteTag/aromaTag는 **반복 query**이며 쉼표/개행/콜론을 분할하지 않는다.
소비자는 각 쌍을 표준 query 인코더로 한 번 인코딩해야 한다. URL·q·sort·page/size를 이 제공자가
추정하지 않으며 기존 필터를 적용할지 교체할지는 Backend/React 연결 계약에서 명시해야 한다.

태그는 이미 정규화한 Backend GET 값을 전제로 한다. 원문·UTF-16 길이·확정 중복을 검증하며
ASCII의 공백/대문자 등 명확한 비정규형은422다. **Python strip/lower로 Java17 전체 Unicode
정규화를 흉내내거나 원문을 바꾸지 않는다.** 선택한 non-ASCII atom에는 반드시
`backend_unicode_revalidation_required=true`와 해당 진단을 붙인다. 예를 들어 k/K가 Backend에서
같아지는지 최종 검증하지 않은 상태로 원문 두 값을 보존한다. Backend의 최종 중복/길이 검증과
400 처리를 소비자가 유지해야 하며 true는 오류율·실제 검색 통과/상품 존재 확인이 아니다.

새 경로에도 기존512KiB 누적 본문·전체10초 수신/연결 종료·object별 중복 key 거절·malformed
우선순위·원문 비반사422를 적용한다. 이는 검색 실행/CPU 작업 시간 보장이 아니다. 모델 라이브러리는
시작/OpenAPI/이 경로에서 import/fit하지 않는다. DB/계정 저장·외부 수집·새 모델·신규 데이터·
랭킹/사람 품질·전체 R06/MVP 완료를 주장하지 않는다.

[검증](TESTING.md) · [동결/실행](plans/2026-11-04-explicit-search-phrases.md)
