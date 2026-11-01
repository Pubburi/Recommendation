# B1 명시 카탈로그 HTTP 계약

`POST /v1/recommendations/content`는 기존 `FittedContentModel`의 **요청 카탈로그 표현 학습과
순위 계산**을 제공한다. 이번 연결 검증은 직접 작성한 허구 입력이다. 서비스 SKU/권리·식별
매핑·서비스 데이터의 실제 fit/관련성·최종 품질 평가·Backend/웹 연동 완료를 뜻하지 않는다.

## 요청과 책임

제공자는 출처·권리·상품 식별/특성을 검수한 후보와 최신 가격·판매 상태를 전달한다. 타입 검증이나
임의 consent flag로 데이터 사용 권한을 승인하지 않는다. 이 API 추가로 legacy80행·이미지의
권리 상태가 바뀌지 않으며 이번에 해당 데이터를 fit하지 않았다. 업무 DB·인증/세션·최종 가용성
재확인은 Backend, 추천의 점수/기여는 Recommendation 소유다. 내부 서비스 계약이며 사용자 ID,
행동 로그·DB/모델 파일 경로·외부 URL·API 키를 입력받지 않는다.

~~~json
{
  "catalog": [
    {"product_id": 1, "available": true, "sku_group": "authored-a", "taste_tags": ["직접 작성 태그"], "abv_percent": 5},
    {"product_id": 2, "available": true, "sku_group": "authored-b", "taste_tags": null, "abv_percent": 15}
  ],
  "profile": {"taste_tags": ["직접 작성 태그"], "preferred_abv_percent": 5},
  "constraints": {"max_abv_percent": 10},
  "limit": 12
}
~~~

위 값은 실제 상품 사실/시세가 아닌 문법 설명용 허구다.

| 필드 | 계약 |
|---|---|
| catalog | 필수·0–1000개, product_id 중복 거절 |
| product_id / available | 1–2,147,483,647 정수 / 필수 boolean |
| sku_group | 필수·trim 후1–128자, 명시 상품군 메타데이터. 이번 요청 안에서 일반화 분할을 수행하지 않음 |
| category / price_krw / abv_percent | 주종1–64자 / 정수0–2,147,483,647 / 유한 수치0–100. 각각 null 허용 |
| taste_tags / aroma_tags | 각각 null 또는 최대20개·trim/lowercase 후1–40자·정규화 중복 거절. null은 미확인, []는 검수 후 선언 태그 없음 |
| volume_ml | null 또는 정수1–1,000,000mL |
| profile | 기본 빈 취향. 선호 categories 최대32개, 맛/향 태그 각각20개, 선호 도수/용량. 모두 soft preference |
| constraints | 기존 [B0](BASELINE-API.md)의 주종·가격/도수 범위·제외 ID. hard 조건이며 취향보다 우선 |
| limit | 기본12, 정수1–100 |

문자열로 숫자/boolean을 대신하거나 알려지지 않은 필드를 추가하면422다. 하한>상한·비유한 값도
거절한다. 가격은 필수 조건 검증용이며 콘텐츠 특성이 아니다. soft category는 hard category로
자동 승격하지 않는다.

## 학습 범위와 응답 의미

전체 명시 catalog로 **요청 안에서만** vocabulary/IDF·관측 수치 변환을 fit하고 같은 catalog를
기존 B1 엔진으로 순위 계산한다. 판매 불가/제외 후보도 명시 카탈로그 표현의 fit에는 포함될 수
있지만, 반환 후보는 필수/제외 조건을 반드시 통과한다. 후보가 적어도 조건을 완화하지 않는다.

이 방식은 known-catalog 표현이다. 학습/검증 상품군 분리·신규 상품 일반화·미래 사용자 선호
학습으로 해석하지 않는다. 데이터 부족 상태를 다른 요청의 vocabulary·scaler·모델로 보완하지 않는다.
동기 route는 FastAPI thread pool에서 실행하며, 모델은 함수 안의 지역 변수로만 유지한다.
시작/health/B0에서는 fit하지 않고 입력·모델·사용자 상태를 저장하지 않는다.
스키마는 NumPy/sklearn을 불러오지 않는 경량 계약으로 분리하고, 비어 있지 않은 B1 요청에서
수치 엔진을 처음 불러온다. 기존 offline content_model의 계약 import 경로는 재노출해 유지한다.

| 응답 필드 | 의미 |
|---|---|
| algorithm | b1-tfidf-minmax-v1 |
| fit_scope | request_catalog |
| representation_fitted | 실제 vocabulary 또는 활성 관측 수치 범위가 있을 때 true. 단순 nonempty/단계 실행 여부가 아님 |
| model_fingerprint | 사용할 표현이 있을 때 요청 fit 문맥의 해시, 그 외 null |
| items | product_id·score0–1·실제 필터/유사도 이유·양의 실제 contributions. 기여 합은 점수와 일치 |
| eligible_count | limit 이전의 적격 후보 수 |
| supported_profile_tokens / unknown_profile_tokens | 요청 vocabulary에서 지원/미등록인 명시 취향 토큰 수 |
| active_numeric_preferences | 관측 범위가 있는 선호 도수/용량 성분 |
| fallback_reason | no_eligible_products / no_supported_preferences / no_matching_features 또는 null |

빈 catalog는 fit 없이 false/null·빈 items·no_eligible_products다. nonempty라도 모든 텍스트가
unknown/빈 태그이고 관측 수치도 unknown/상수뿐이면 false/null로 실제0과 미확인을 보존하면서
결정적 B0 순서를 반환한다. 표현은 있지만 취향이 비어 있거나 OOV이면 true와 해당 모델 해시를
유지할 수 있으며 no_supported_preferences·0점/기본순을 반환한다. 적격 후보에 공유 특성이 없으면
no_matching_features로 구분한다. 점수는 예측 만족 확률이나 추천 품질 성과가 아니다.

## HTTP·원문 경계

두 추천 POST는 실제 수신 원문 **524,288B(512KiB)**를 초과하면413, 전체 본문 수신이10초를
넘으면408 고정 JSON을 반환한다. 잘게 나눠 보내도 크기는 누적하고 시간 예산은 갱신하지 않는다.
본문 수신 중 연결 종료가 확인되면 파싱/fit하지 않는다. 이 예산은 본문 수신용이며 CPU fit
취소/완료의 시간 보장이 아니다.
카탈로그·태그·문자열·원문 상한으로 실행 입력을 제한한다.

422 진단에는 type/loc/msg만 포함해 원문 카탈로그·비유한 값·개인 데이터를 다시 내보내지 않는다.
기존 health/B0·프로세스 가용성 의미는 유지한다. 새 wheel의 실제 HTTP·부분 본문408·입력 오류와
요청 간 격리는 [검증 안내](TESTING.md)에서 확인한다. 전후 지연/품질 개선을 주장하지 않는다.

공식 근거: [FastAPI 동기 route/thread pool](https://fastapi.tiangolo.com/async/),
[Python asyncio timeout](https://docs.python.org/3.12/library/asyncio-task.html#asyncio.timeout),
[기존 B1 수식/unknown/기여](CONTENT-MODEL.md).
