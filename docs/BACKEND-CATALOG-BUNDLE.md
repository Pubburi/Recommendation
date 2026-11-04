# 검수 카탈로그의 Backend 소비 bundle

`python -m pubburi_recommendation.backend_catalog_bundle`은 기존
[checked export](CHECKED-EXPORT-ACCEPTANCE.md)의 정확한 catalog와 명시 업무 매핑/원응답을
단일 JSON으로 발행한다. Backend는 운영자가 선택한 파일 path와 전체 바이트 SHA256을 pin하고
현재 업무 값을 재확인한다. Java가 원천 검수·권리 loader·fit을 복제하지 않는다.

현재 scope는 **DEMO 소비 연결**이다. `service_catalog_approved=false`, `model_loaded=false`,
`current_business_revalidation_required=true`를 고정한다. 기존 source11·container DEMO1·
별도 family browse DEMO5의 grain/권위는 바뀌지 않는다. legacy80/sourceName/URL·임의 동의
flag를 근거로 승인 ID를 추가하지 않는다. 파일 hash는 운영자 설정의 무결성 pin이며 서명이나
권리/발행자 인증이 아니다. 신뢰할 원권위를 검수해 선택하는 책임은 계속 운영자에게 있다.

## 정확한 v1 구조

`BackendCatalogBundle`의 최상위는 다음9개 필드만 갖고 전부 필수다.

| 필드 | 계약 |
|---|---|
| schema_version | 정수1 |
| algorithm | `checked-backend-demo-bundle-v1` |
| catalog | 검증한 B1 export의 ContentProduct 배열 그대로.1–1000개, 중복 ID 없음 |
| records | 같은 catalog ID/순서의 아래7필드 배열. source key/업무 ID는 각각 유일 |
| checked_export | 기존 checked metadata 전체. 아래14개 필드 |
| service_catalog_approved / model_loaded | 각각 엄격 boolean false |
| current_business_revalidation_required | 엄격 boolean true |
| valid_until_utc | 원 business snapshot.capture_finished_at_utc +300초의 UTC 시각 |

각 records 항목은 `catalog_record_id`, `backend_product_id`, `sku_group`, `price_kind`,
`eligibility_scope`, `product`, `features`만 갖는다. source key/ID/group은 기존 명시 mapping에서
복사한다. price_kind는 `demo_snapshot_krw`, eligibility_scope는 기존
`public_browse_row_exists` 또는 별도 `reviewed_source_family_browse_demo_only`다.
`product`/`features`는 [Product7/features8 성공 ApiResponse](BUSINESS-EXPORT.md)의 원 parsed
JSON 전체다. DTO로 확인한 뒤 원 객체를 보존하며 description/source 문자열·null/[]·배열순서나
숫자를 다시 모델 입력으로 확장하지 않는다. 모델에는 기존 검수 catalog만 전달한다.

checked_export의 정확한14개 필드는 `algorithm`, `mode`, `checked_at_utc`,
`original_export_at_utc`, `snapshot_origin`, `data_scope`, `evidence_kind`,
`source_catalog_sha256`, `business_snapshot_sha256`, `mapping_sha256`, `artifact_sha256`와 위3개
boolean이다. algorithm은 `checked-reviewed-demo-export-v1`, mode는 `fresh_demo_snapshot`이다.
artifact_sha256에는 원 receipt/report/B0/B1 네 파일 이름과 SHA가 모두 있다. 다른 mode나
승격된 boolean·추가 필드는 v1 계약에 맞지 않는다.

catalog의 ID/그룹·주종/가격/도수/용량은 해당 원응답·명시 그룹과 일치해야 한다. 기존 원천의
미확인 taste_tags/aroma_tags=null과 family-only volume=null을 유지한다. 업무 태그·소개·이미지·
주문 수를 새 학습 사실로 승격하지 않는다. 같은 그룹의 복수 변형 자체를 금지하지 않는다.

## 시계와 소비 책임

완료 발행 전에 원 authority·mapping/snapshot과 완료 export4파일을 **다시** 검증한다. source/
snapshot/mapping/artifact hash 변경을 거절한다. source receipt/hash를 검수하는 loader는
Recommendation에 하나만 유지한다. 원 snapshot의5분 예산을 발행 시각부터 다시 시작하지 않는다.
valid_until은 최종 checked_at보다 엄격히 늦고 그 차이는300초 이하여야 한다. 현재 시각에 이미
만료됐다면 완료 발행하지 않는다. runtime용 CLI에는 `--replay`가 없다.

Backend는 pin SHA·엄격 구조·ID/group/catalog binding을 확인하고 historical mode·만료·변조/
부적절한 입력은 provider 전송 없이 거절한다. 매 요청에서 pin한 records의 **현재 업무 public
Product7/features8 전체 필드**를 같은 ID로 비교한다. 문자열/null/[]/배열순서는 그대로,
숫자는 유한한 exact decimal 값으로 비교한다. Python의 parsed response provenance hash를
다른 숫자 직렬화 규칙으로 다시 만들어 권위 검사를 복제하지 않는다. 불일치는409/fail-closed이며
부족분을 다른 미승인 행으로 채우지 않는다. upstream preferences를 더한 실제 본문도 기존512KiB
이내여야 한다. 판매/재고·두 API의 원자 snapshot/서버 revision 보장은 새로 생기지 않는다.

## 발행

~~~bash
uv run --locked python -m pubburi_recommendation.backend_catalog_bundle \
  --export-dir .pubburi/current-export \
  --manifest sources/wikidata-structured.json \
  --input .pubburi/source/raw.json --source-receipt .pubburi/source/receipt.json \
  --curation .pubburi/source/curation.json \
  --business-snapshot .pubburi/current-business-snapshot.json \
  --mapping .pubburi/current-explicit-mapping.json \
  --output-dir .pubburi/new-backend-bundle
~~~

family scope에는 원래 `--family-review`도 필수다. 새 private 출력만 허용한다. 완료 출력은
`catalog-bundle.json`과 `receipt.json`이며 receipt.completed=true·bundle_sha256·records·
valid_until_utc를 확인한 뒤 운영자가 파일과 SHA를 함께 pin한다.10MiB 상한을 유지한다.
기존 출력/예상 밖 target을 덮거나 지우지 않고, 실패/만료/중간 변경이면 승인 bundle을 발행하지
않는다. receipt의 완료와 service_catalog 승인/모델 학습·사용자 품질을 혼동하지 않는다.

원천·업무 원응답/매핑/bundle은 ignored private에 둔다. 새 모델·startup catalog나 endpoint가
추가되지 않는다. Backend의 현재 계정 권한/취향·fallback·React 연결과 현재 서비스 카탈로그/
명시 권리·필드/실제 fit·독립 평가의 전체 인수는 별도 필수 작업이다.

[실행 계획](https://github.com/Pubburi/Recommendation/blob/39647aab11e2bb212a23162ad1c57596860b32a7/docs/plans/2026-11-04-backend-catalog-bundle.md) · [검증](TESTING.md)
