# 기준 상품의 유사 후보 API — R03 추천 제공자

`POST /v1/recommendations/similar`는 명시한 기준 상품의 검수 사실로 기존 B1
`FittedContentModel.similar`를 호출한다. 사용자 취향·구매 통계나 장바구니 맥락을 추정하지 않는다.
기존 B0/content/exploration은 그대로이며 Backend·상품 상세 화면과 전체 R03은 아직 연결하지 않았다.

## 요청과 소유권

```json
{
  "catalog": [],
  "reference_product_id": 1,
  "constraints": {},
  "limit": 12
}
```

- `catalog`는 [content 계약](CONTENT-API.md)의 `ContentProduct` 최대1000개이며 빈 목록을 허용한다.
  명시 Backend 상품 ID와 검수 `sku_group`, nullable 주종/가격/도수/용량·맛/향을 그대로 받는다.
  상품 이름·브랜드·원천 entity ID로 그룹이나 맛/향을 생성하지 않는다. 중복 상품 ID는 거절한다.
- `reference_product_id`는 필수 정수1–2,147,483,647이며 이 catalog 안에서 기준 상품을 찾는다.
  문자열·boolean·범위 밖 ID는422다. 별도 `profile`이나 알려지지 않은 필드는 허용하지 않는다.
- `constraints`는 기존 B0와 같은 주종·가격/도수 범위·제외 ID의 hard 조건이다. 기준 상품의
  주종은 soft 유사도 근거이며 후보의 필수 주종으로 자동 승격하지 않는다.
- `limit`은 기본12, 정수1–100이다. 부족한 후보를 채우려고 reference/변형·hard 탈락·0점을 복구하지 않는다.

원천 권리·사실/상품 식별·현재 가격과 판매 상태 검수는 호출자 책임이다. 인증/업무 DB와 반환 뒤
최신 판매 상태/제외 재확인은 Backend가 담당한다. 제공자에 사용자 ID/로그·DB/모델 파일 경로·
외부 URL/키·동의 flag를 전달해 권리를 대신 승인할 수 없다. 기존80개 시드/자산의 감사 상태를
바꾸거나 이를 새로운 학습 카탈로그로 자동 채택하지 않는다.

## 처리와 응답

1. 기준 ID가 없거나 `available=false`면 수치 런타임을 import/fit하지 않는다. 빈 items와 명시
   `reference_not_in_catalog` 또는 `reference_unavailable`을 반환한다. 업무 데이터의 누락/삭제를
   임의의 기준 상품이나 인기순 '유사 상품'으로 대체하지 않는다.
2. 정상 기준이면 전체 명시 catalog로 요청 안에서 vocabulary/IDF·관측 수치 범위를 fit한다.
   기준/판매 불가/제외 후보도 알려진 카탈로그 표현 fit에는 포함될 수 있다. 같은 명시
   `sku_group`의 모든 항목을 후보에서 제거한 뒤 기존 `similar`를 호출한다. 같은 그룹 내부 변형을
   별도 유사 상품으로 재노출하지 않으며 내부 제거가 호출자의1000개 제외 ID 예산을 소비하지 않는다.
3. 기준의 주종/맛/향과 관측 도수/용량만 기존 B1 profile로 바꿔 순위를 계산한다. unknown은0이나
   추정 사실이 아니고, 상수 수치 범위는 거리로 쓰지 않는다. 가격은 hard 조건용이며 유사도 성분이 아니다.
4. 반환 items에는 양수 유사도만 남긴다. 기존 B1 항목의 score/reasons/contributions는 수정하지 않는다.
   같은 그룹이 아닌 후보들 사이에 별도 MMR·상품군당1개 정책은 적용하지 않는다.

기존 B1 응답의 `algorithm=b1-tfidf-minmax-v1`·fit_scope/representation_fitted/model_fingerprint와
items·설명/기여를 사용한다. `supported_profile_tokens`, `unknown_profile_tokens`,
`active_numeric_preferences`는 이 API에서 **기준 상품의 사실로 만든 profile**의 지원/수치 성분이다.
사용자에게 학습한 취향이나 구매 선호라는 뜻이 아니다. 기여 합은 원래 B1 점수이며 만족 확률이 아니다.

| 추가/구분 필드 | 의미 |
|---|---|
| reference_product_id / reference_sku_group | 요청한 기준 ID / 확인한 명시 그룹. 기준이 없으면 그룹 null |
| reference_state | missing / unavailable / available |
| profile_source | reference_product_facts |
| reference_group_policy | exclude_reference_group |
| excluded_reference_group_count | 정상 기준에서 후보로 제거한 같은 그룹 수. 본인도 포함. 미계산이면 null |
| eligible_count | 정상 기준의 그룹 제거와 hard 조건 뒤, 양수/limit 전 후보 수. 기준이 없거나 사용 불가면 **미계산 null** |
| fallback_reason | reference_not_in_catalog / reference_unavailable 또는 기존 no_eligible_products / no_supported_preferences / no_matching_features |

기준 부재/판매 불가는 representation_fitted=false·fingerprint=null이다. nonempty catalog에 fit했어도
쓸 어휘/활성 수치 범위가 없으면 false/null을 유지한다. 기준의 지원 특성이 없거나 적격 후보에
공유 근거가 없으면 빈 items와 기존 fallback 사유를 반환한다. 전체 fit 표현이 존재해도 유사 후보가
있다는 뜻은 아니며, `eligible_count`가 items 수보다 클 수 있다.

모든 fit은 request_catalog의 known-catalog 표현이다. 사용자 선호 학습·신규 SKU 일반화·held-out
평가가 아니고, 다른 요청의 모델/어휘·기준 상품을 재사용하지 않는다. 새 R07 공동구매/연관 구매
통계나 R08 다양성 선택을 구현했다고 표시하지 않는다.

## HTTP·검증과 한계

다른 추천 POST와 같은512KiB 누적 원문·전체10초 본문 수신 기한과 object별 중복 JSON key의
고정422를 적용한다. malformed·인코딩/깊이·media별 기존 오류 우선순위를 유지하고 입력값을
검증 오류에 반사하지 않는다. 이 수신 기한은 CPU fit 취소/완료의 보장이 아니다.

시작/스키마/health와 기준 부재·판매 불가 처리는 NumPy/sklearn·DB/모델 다운로드/외부 키를
요구하지 않는다. 런타임-only 새 wheel의 실제 HTTP와 OpenAPI·부분 본문408까지 검증한다.
허구 사실의 독립 고정 조건·원점수 보존·실제 실행/한계는 [작업 기록](plans/2026-11-02-similar-product-provider.md)에 둔다.
새 실서비스 원천/업무 매핑·카탈로그 fit/관련성 품질·최종 R03 Backend/화면 연결 완료는 아니다.
