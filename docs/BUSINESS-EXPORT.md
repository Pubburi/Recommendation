# 원천과 업무 상품의 명시 시연 매핑

`python -m pubburi_recommendation.business_export`는 검수 원천과 업무 스냅샷의 명시 매핑으로
B0/B1 **오프라인 시연 요청**을 만든다. 이름·QID·바코드·행 순서로 업무 ID를 찾거나 상품을
생성하지 않는다. 요청 자동 전송·모델 fit·업무 DB 저장은 하지 않는다.

## 업무 스냅샷

Backend 소유의 기존 GET `/api/products/{id}`와 GET `/api/products/{id}/features`를 사용한다.
[ProductResponse](https://github.com/Pubburi/Backend/blob/main/src/main/java/com/pubburi/pub/controller/response/ProductResponse.java)의
`id/name/type/price/img/abv/orderCount`7필드와 [특성 계약](https://github.com/Pubburi/Backend/blob/main/docs/PRODUCT-FEATURES.md)의
`productId/volumeMl/description/tasteTags/aromaTags/sourceName/sourceUrl/sourceNote`8필드를
각 `data/message/error` ApiResponse로 엄격히 받는다. 성공 `error=null`, 같은 양의 정수 ID·
중복 없음·유한 수치 범위/nullable 타입을 확인하며 bool/실수/문자열 ID를 변환하지 않는다.

```text
schema_version: 1
snapshot_origin: demo_fixture | owned_demo_fixture | existing_local_catalog
capture_method: authored | http_read
capture_started_at_utc / capture_finished_at_utc: UTC timestamp
records: [{product: <7필드 성공 ApiResponse>, features: <8필드 성공 ApiResponse>}]
```

`demo_fixture`는 `authored`, 나머지는 `http_read`와 짝지어야 한다. origin은 수집자의 명시
기록이며 CLI가 HTTP 실행/발행자를 인증하지 않는다. 별도 수집 근거를 보존한다. fixture
원천은 두 fixture origin에만, 공개 원천은 `existing_local_catalog`에만 매핑한다.

제공자에 상품/특성 ETag·revision·판매/재고 필드가 없으므로 전체 응답 content hash·시각은
서버 revision이나 두 GET의 원자적 읽기가 아니다. 캡처 구간0–60초·미래 금지·export 직전까지
종료 시각에서5분 이내를 요구한다. 이것은 로컬 스냅샷 정책이며 실시간 판매/재고·동시 수정
보장이 아니다. 소비 Backend는 현재 행·가격·필수/제외 조건을 다시 확인해야 한다.

## 매핑과 정본

명세는 `algorithm=reviewed-business-demo-export-v1`, source catalog content hash,
business snapshot **파일 hash**, UTC 검수 시각, records를 가진다. 검수는 캡처 종료 뒤,
실행 시각 이전이어야 한다. source catalog는 생성 파일을 단독 신뢰하지 않고 허용
manifest·raw/receipt/curation에서 [같은 파이프라인](SOURCE-CATALOG.md)으로 다시 계산한다.

| 필수 매핑 필드 | 의미 |
|---|---|
| catalog_record_id·backend_product_id | 입력에 존재하는 두 ID를 명시하며 각각 한 번만 매핑 |
| product_response_sha256·features_response_sha256 | 원응답 전체 parsed JSON의 정렬 키/compact/UTF-8 content hash. HTTP 원바이트 hash가 아님 |
| source_variant_group | 원천 검수의 명시 그룹과 정확히 일치 |
| eligibility_scope | `public_browse_row_exists`. 캡처 행의 공개 탐색 목적이며 판매/주문/재고 검증 아님 |
| demo_browse_eligible | 명시 bool. false/unknown을 true로 추정하지 않음 |
| price_kind | `demo_snapshot_krw`. 원천 관측 판매가가 아닌 업무 시연 가격 |
| identity_review_note | 수동 동일성 근거. 해시/사실 검사를 덮거나 권리를 승인하지 못함 |

업무 도수·known 용량은 source와 정확히 같아야 한다. 미확인 업무 용량을 몰래 채우지 않는다.
wire의 ID·주종·시연 가격은 업무 응답, 도수/용량·그룹은 일치가 확인된 원천/검수를 따른다.
source unknown인 맛·향은 null이다. 업무 설명/태그/이미지/주문 수/URL을 모델 입력으로
가져오지 않으며 sourceName/URL도 권리 승인이 아니다. 변경 응답·참조/그룹·unknown/수치
불일치·stale/미래·origin 혼합은 내보내기를 거절한다. API-origin URL/세션/키는 입력에 없다.

매핑이 없으면 `no_mapping_provided`·0건만 기록하고 요청 파일을 만들지 않는다. 오래된
스냅샷은 무매핑 감사에 읽을 수 있지만 fresh export로 부르지 않는다. 미래/역전/과도한 캡처
구간과 잘못된 스키마는 무매핑 상태에서도 거절한다.

## 실행·완료

```bash
uv run --locked python -m pubburi_recommendation.business_export \
  --manifest sources/wikidata-structured.json \
  --input .pubburi/source/entities.json \
  --source-receipt .pubburi/source/receipt.json \
  --curation .pubburi/catalog-curation.json \
  --business-snapshot .pubburi/business-snapshot.json \
  --mapping .pubburi/reviewed-mapping.json \
  --output-dir .pubburi/business-export-new
```

`--mapping`은 선택이다. 새 ignored 디렉터리에 `export-report.json`과 완료 receipt를 쓴다.
매핑된 상품이 있을 때만 `b0-demo-request.json`·`b1-demo-request.json`을 만든다. 일부 쓰기나
마지막 freshness 검사 실패는 완료로 표시하지 않고 기존 출력을 덮지 않는다. 소비자는
`receipt.completed=true`를 먼저 확인한다. 원문/스냅샷/매핑/요청·로컬 로그는 Git/CI artifact에 넣지 않는다.

## 실제 관측과 한계

2026-11-01 별도 전용 DB/업무 API로 만든 **허구 DEMO상품1개**를 실제 읽어 명시 매핑했다.
API가 반환한 ID로 각 B0/B1 요청에1개 상품을 내보내고 동적 loopback 추천 서버에 산출물을
보내 HTTP200·같은 ID·적격1개를 확인했다. 업무 API/추천 wire 검증이며 실제 주류/사용자
선호·매출 품질로 집계하지 않는다. CI의 전부 authored snapshot 검증과도 구분한다.

별도로 실제 CC0 원천4항목→검수 후보1개와 기존 업무80개 스냅샷은 무매핑/요청파일0이다.
이름/순서로 대응을 만들지 않았다. 실제 허용 서비스 SKU·실매핑·서비스 B1 fit·독립 관련성/
최종 평가는 미완료다. 이번 결과는 학습/품질·판매/재고·성능·서버 revision 완료가 아니다.

[구현](../src/pubburi_recommendation/business_export.py) ·
[회귀](../tests/test_business_export.py) ·
[작업/검증](plans/2026-11-01-reviewed-business-export.md)
