# R04 opt-in 사실 설명 계약

기존 B1 `content`, `exploration`, `similar`, `context`, `feedback` POST에
`include_explanations: true`를 주면 item에 `explanation`을 추가한다. 기본값은 false이며
엄격 boolean만 허용한다. null·숫자·문자열은422다. 생략/false에는 새 필드를 직렬화하지 않아
기존 전체 응답을 보존한다. B0 `/baseline` 계약에는 이 옵션을 추가하지 않는다.

설명은 **원래 점수/기여와 요청 사실의 표현**이다. fit·점수·순서·필수/제외·fallback·MMR 정책을
바꾸거나 모델/LLM·HTML·DB·외부 데이터를 추가하지 않는다. 기존512KiB 누적 수신/10초
deadline·limit100·startup 무모델도 유지한다. 수신 deadline은 CPU fit 시간 보장이 아니다.
제공자 증가분이며 Backend/React 표시·전체 R04와 기능 완료 수는 별도로 검증한다.

## 공식 schema와 비교 출처

실행 OpenAPI의 `ItemExplanation`과 evidence의 `kind` discriminator가 소비 계약이다.
[경량 DTO](../src/pubburi_recommendation/content_contracts.py)와
[formatter](../src/pubburi_recommendation/content_explanations.py)가 구현한다.

| 필드 | 의미 |
|---|---|
| version | r04-facts-v1 |
| basis | content_similarity / deterministic_baseline / no_shared_features |
| comparison | kind=profile 또는 kind=reference_product와 실제 product_id |
| score_evidence | 원래 양수 기여 상위 최대3개. kind·고정 한국어 label·actual_value/target_value·원 contribution, 수치에는 단위 |
| total_positive_contributions | 원래 양수 기여 전체 개수, 최대43 |
| score_evidence_truncated | 전체가3개를 넘으면 true. 표시한 일부의 합을 전체 score라고 표시하지 않음 |
| filter_evidence | 입력 가용성과 실제 활성 주종/가격/도수 hard 조건, 최대4개 |
| fallback_reason | 원래 B1 비교의 no_eligible_products / no_supported_preferences / no_matching_features 또는 null |

직접 profile과 탐색의 B1 근거는 profile 비교다. similar/context와 피드백의 positive 승자는
실제 기준 ID를 보존한다. 피드백 동점에서 profile이 이기면 profile이다. reference 사실을
사용자 취향으로 부르지 않는다. context의 한 기준 최대 매치와 exploration의 별도 다양성
selection metadata도 구분한다.

## 점수 근거

| kind / 고정 label | actual/target 및 단위 |
|---|---|
| category_match / 주종 일치 | 실제 사용한 주종과 같은 명시 비교 값 |
| taste_match / 맛 태그 일치 | 양쪽에 있는 같은 canonical 맛 atom |
| aroma_match / 향 태그 일치 | 양쪽에 있는 같은 canonical 향 atom |
| abv_comparison / 도수 비교 근거 | 관측 도수와 실제 비교 목표·vol% |
| volume_comparison / 용량 비교 근거 | 관측 용량과 실제 비교 목표·mL |

상위 선택은 contribution 내림차순, 정확 동점은 원래 component/feature 순이다. 원래 값과
기여를 재가중/반올림하지 않는다. 모든 기존 contributions와 합/score 계약은 그대로다.
label은 위 enum이며 값은 typed 데이터다. 기존 trim/lowercase 이후 atom 안의 쉼표·개행·
콜론을 통째로 보존하며 다시 분할/요약하지 않는다. 소비 화면은 값을 텍스트로 표시한다.

unknown 수치·비활성 상수 열·OOV/빈 태그에는 점수 근거를 만들지 않는다. 실제0과 null을
구분하고 양수 기여가 있을 때만 수치 actual/target을 노출한다. 가격은 점수 특성이 아니다.
formatter는 모든 양수 기여의 사실/합과 hard 코드를 대조한 뒤 최대3개를 표시한다.
모순된 기여나 사용하지 않은 사실을 그럴듯한 문장으로 보완하지 않는다.

## 필터·fallback과 상한

- availability_filter의 `입력 가용 조건 충족`은 요청 available=true이며 실제 판매/재고
  확인이나 권리 승인이 아니다.
- category_filter는 실제 통과 주종·중복을 제거한 허용 주종 개수다. 가격/도수는 actual_value·
  minimum/maximum과 KRW/vol%다. 미지정 bound는 null이며 label은 `입력 주종 조건 충족`·
  `입력 가격 조건 충족`·`입력 도수 조건 충족`이다. DEMO/실판매가·최신성을 추정하지 않고
  제외 ID 목록을 복사하지 않는다.
- 0점에는 score_evidence가 없다. 원래 결정적 기본순은 deterministic_baseline과 정확한
  fallback, 다른 양수 후보 옆의 공유 근거 없는 행은 no_shared_features다. B0/OOV/무정보
  0점을 선호 근거로 표시하지 않는다. 반환 item이 없으면 설명도 없다.
- label은 고정이며 actual/target atom을 자르지 않는다. 생략된 기여는 count/truncation으로
  밝힌다. 각 설명 JSON은 UTF-8로4096B 이하이며 최종 reference ID 반영 뒤에도 확인한다.
  limit100에서 설명 객체 합은 최대409600B와 고정 JSON 필드 구조다. 요청512KiB와 응답
  설명 객체 크기는 서로 다른 경계다.

권리·가격·상품군/물리 SKU·family-browse DEMO의 권위는 이 옵션으로 바뀌지 않는다.
사용자 선호 품질·성능·전체 R02/R04·Backend/웹 완료 근거로 확대하지 않는다.
[검증](TESTING.md) · [동결/실행](https://github.com/Pubburi/Recommendation/blob/39647aab11e2bb212a23162ad1c57596860b32a7/docs/plans/2026-11-03-factual-explanations.md)
