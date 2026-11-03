# R05 명시 피드백 추천 계약

선택적 `include_explanations: true`는 [R04 사실 설명](EXPLANATIONS.md)을 추가한다.
엄격 boolean/기본false이며 생략/false에는 기존 응답을 보존한다. 원점수·순서·fit/정책을
바꾸지 않고 profile/실제 winning 기준 ID의 사실을 구분한다.

`POST /v1/recommendations/feedback`은 명시한 취향과 **맞음/관심 없음 상품 ID**를 현재 카탈로그의
검수 사실에 적용한다. 기존 B1의 fit/rank/similar를 재사용하며 새로운 사용자 학습 모델이나
공동구매 통계를 만들지 않는다. R05 추천 제공자 증가분이며 저장·계정 권한·Backend/웹 연결과
전체 R02/R05 완료, 서비스 카탈로그 fit·사용자 품질을 뜻하지 않는다.

## 요청과 소유권

~~~json
{
  "catalog": [
    {"product_id": 1, "sku_group": "authored-a", "available": true, "taste_tags": ["직접 작성 태그"]},
    {"product_id": 2, "sku_group": "authored-b", "available": true, "taste_tags": ["직접 작성 태그"]}
  ],
  "profile": {},
  "feedback": {"positive_product_ids": [1], "not_interested_product_ids": []},
  "constraints": {},
  "limit": 12
}
~~~

위는 실제 상품/행동이 아닌 자체 문법 예다. catalog/profile/constraints/limit은 기존
[content 계약](CONTENT-API.md)과 같다. feedback은 생략 가능하며 두 ID 목록의 기본값은[]다.
각 목록은 최대20개·서로 중복 없는 엄격한1–2,147,483,647 정수다. 목록 사이 같은 ID나 검수
그룹이 겹치면 관심 없음이 우선한다. 잘못된 타입·중복·상한·알려지지 않은 필드는422다.
빈 목록은 명시 피드백 없음이며 null은 거절한다. catalog의 중복 ID는 제외 전에 거절한다.

Backend가 본인 계정의 저장/수정/삭제·권한·최신 가격/판매 상태를 검증하고 명시 신호를 전달한다.
찜/평점의 positive 변환·임계값은 이번 계약에 정하지 않았으며 임의 평점/빈도 가중치를 만들지
않는다. 원래 profile과 positive 상품 사실은 별도 점수 출처로 남긴다. 사용자 ID·로그·DB/모델
경로·외부 URL을 받거나 저장하지 않으며 제공 카탈로그의 권리/정체성을 자동 승인하지 않는다.

## 제외와 점수

1. 모든 not_interested ID와 알려진 해당 sku_group의 모든 후보를 먼저 제외한다. 판매 불가
   기준 상품의 가용 변형도 제외한다. 없는 ID는 그룹을 추정하지 않고 그 ID만 제외한다.
2. 알려진 모든 positive 기준 그룹도 후보에서 제외한다. unavailable/negative 충돌 기준의
   그룹도 포함한다. 이미 맞다고 한 상품의 대안을 찾는 정책이며 원천 QID를 SKU로 승격하지 않는다.
3. 기존 판매 상태·hard 주종/가격/도수·exclude_product_ids를 그대로 적용한다. 내부 제외가
   기존1000개 hard ID 예산을 소비하지 않으며 후보 부족/피드백 때문에 조건을 완화하지 않는다.
4. 명시 전체 catalog를 요청 안에서 **한 번** fit한다. 기존 content와 같이 제외/판매 불가
   상품도 카탈로그 표현 fit에는 포함될 수 있다. 음성 신호는 그 사실을 negative 선호 벡터로
   만들지 않으며, 알려진 negative 그룹의 positive 기준은 점수 자료로 사용하지 않는다.
5. explicit profile은 기존 rank, available·negative 비충돌 positive 상품은 기존 similar로
   같은 후보에 점수를 계산한다. 후보별 최대 양수 점수와 그 출처의 원래 이유/contributions를
   선택한다. 정확한 동점은 profile → 작은 positive ID 순이고 최종 순서는 점수 내림차순/ID
   오름차순 후 limit이다. 반복 신호/같은 사실의 변형 수를 합산·인기도로 보상하지 않는다.

positive 사실의 지원 text token이나 활성 관측 수치가 있으면 informative로 센다. 태그
null/[]는 원래 의미를 보존하고 모르는 맛/향을 추론하지 않는다. 실제 도수0은 관측값이고
null은 수치 유사도 근거가 아니다. 단일 상품/상수 수치에는 원래 B1처럼 거리 scale이 없다.

## 응답과 두 fallback 경로

| 필드 | 의미 |
|---|---|
| algorithm / feedback_algorithm | b1-tfidf-minmax-v1 / r05-max-explicit-feedback-v1 |
| fit_scope / representation_fitted / model_fingerprint | 기존 request_catalog/사용 가능한 표현 여부/그 해시. 빈 catalog는 fit 없이 false/null |
| feedback_group_policy | exclude_all_known_feedback_groups |
| positive_references | ID 순. missing / blocked / unavailable / available 상태와 알려진 그룹. blocked는 negative 충돌을 우선 표시 |
| positive별 지원/OOV·활성수치·fallback | 평가했을 때 기존 similar의 진단. missing/blocked/unavailable는 미평가 null이며 무정보의0/[]와 구분 |
| not_interested_references | ID 순. missing/unavailable/available 및 알려진 그룹. missing 그룹은 null |
| evaluated_positive_count / informative_positive_count | available·비충돌 평가 수 / 그중 지원 text·활성 수치가 있는 수 |
| excluded_not_interested_count | hard 적용 전 negative ID/그룹으로 제외된 카탈로그 행 수 |
| excluded_positive_group_count | 그 다음 positive 그룹으로 제외된 행 수. negative 중복을 다시 세지 않음 |
| eligible_count | 모든 그룹/ID 제외·hard 조건 뒤, limit 이전 후보 수 |
| supported_profile_tokens / unknown_profile_tokens / active_numeric_preferences | explicit profile의 기존 진단. positive별 값과 합산하지 않음 |
| matches | items와 같은 순서의 출처 profile / positive_feedback / baseline. positive_feedback에만 positive_product_id |
| items | 기존 B1 원점수·실제 이유/기여. positive 최대 선택이 기여를 재가중하지 않음 |

- `ranking_mode=positive_feedback`: informative positive가1개 이상이다. profile/positive 중
  양수만 반환하고 부족분을0점으로 채우지 않는다. 공유 근거가 없으면 빈 items/matches와
  no_matching_features다. 기존 profile의0점 B0 순서를 positive 근거로 표시하지 않는다.
- `ranking_mode=profile_fallback`: informative positive가 없다. 원래 profile.rank의
  items·fallback을 보존한다. 명시 취향이 비어 있거나 OOV면 no_supported_preferences,
  공유 특성이 없으면 no_matching_features의 결정적0점 기본순일 수 있다. 해당 행의 match는
  baseline이며 선호 근거가 아니다. profile의 양수 행만 profile로 표시한다.
- 두 경로 모두 후보0이면 빈 결과/no_eligible_products다. 빈 catalog도 동일하며 수치 runtime을
  import/fit하지 않는다. 결과가 짧거나 비어도 negative/hard 조건은 유지한다.

시작/health/B0·기존 content/context의 응답·정책을 보존한다. 새 경로도512KiB 누적 원문·10초
전체 수신 deadline·중복 decoded JSON key 거절·기존 문법 오류 우선순위와 비반사422 진단을
적용한다. CPU fit 시간 제한/취소 보장은 아니다. 요청마다 모델/피드백은 지역 변수이며 요청 간
공유·저장하지 않는다. [회귀/격리 wheel 실제 HTTP](TESTING.md)는 자체 사실의 계약 검증이며
사용자 선호 적중률·전환율·서비스 품질/성능 성과로 바꾸지 않는다.
