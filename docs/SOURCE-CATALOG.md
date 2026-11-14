# 검수한 원천 포장 카탈로그

`python -m pubburi_recommendation.source_catalog`는 허용된 구조화 원천과 별도의 수동 검수
명세를 읽어 **포장 후보의 원천 카탈로그**를 만든다. 브랜드/용기 분류가 섞인 원천을 그대로
업무 SKU로 등록하지 않고, 이번에 해석한 단위·근거와 원래 충돌을 함께 남긴다.
문자열 `catalog_record_id`·`source_variant_group`은 Backend ID나 판매 적격성 승인이 아니다.

## aT 검수 사실의 로컬 카탈로그 권위

`python -m pubburi_recommendation.at_local_catalog`는 기존 aT CSV·원 획득 receipt·행별
동일 제공자 근거·단일 포장 검수를 재검증해 `at-reviewed-local-catalog-v1`을 발행한다.
이는 비상업 로컬 MVP의 구조화 사실 표시/fit 범위를 명시한 프로젝트 정책이다. 포털의
무료/제한 없음 표시와 추가 유의사항을 함께 검토한 기존 이용 범위를 사용하며 새로운
외부 권리 취득, 실제 판매 적격성이나 GTIN 확인으로 표현하지 않는다. 원문·이미지·창작
소개·미확인 맛/향·실판매 가격·재고는 포함하지 않는다.

```bash
uv run --locked python -m pubburi_recommendation.at_local_catalog \
  --manifest sources/at-traditional-liquor.json \
  --input .pubburi/source/public-data.csv --receipt .pubburi/source/source-receipt.json \
  --review .pubburi/catalog/review.json --selection .pubburi/catalog/selection.json \
  --fact-evidence .pubburi/catalog/provider-evidence.html \
  --output-dir .pubburi/catalog/new-authority
```

selection은 `schema_version=1`, `algorithm=at-local-catalog-selection-v1`, `catalog_version`,
실제 로컬 재검수 `reviewed_at_utc`, raw/원 receipt/현재 manifest/새 review의 파일 SHA256,
`records[{catalog_record_id,source_row_number,source_variant_group}]`를 가진다. 선택 행은 review와
정확히 같아야 한다. 고유 record ID/행을 요구하고 변형 그룹은 명시적으로 공유할 수 있다.
라벨·양조장·단일 도수·단일 mL가 모두 검수됐으며 CSV와 정확히 같은 행만 통과한다.
기존 보류·복수 수량·동일 라벨/양조장 중복을 이 선택으로 덮지 않는다.
선택 행이 참조한 출판물 자체에 공공누리 제3·4유형이나 변경 금지 표시가 있으면 로컬 권위 발행을 보류한다.
검수자는 각 출판물의 이용 조건과 원천 범위를 직접 확인한다.
출처 URL은 Backend도 읽을 수 있는 더술닷컴의 `https` 출판물 주소여야 한다. 잘못된 URL 인코딩이나
fragment가 있으면 발행 전에 거절하고, 유효한 주소와 query는 그대로 보존한다.

출력 `catalog-authority.json`의 추가 필드는 거절하며 정확 계약은 다음과 같다.

| 필드 | 내용 |
|---|---|
| root | `schema_version:1`, `algorithm:at-reviewed-local-catalog-v1`, `scope:REVIEWED_LOCAL_CATALOG`, `catalog_version`, `reviewed_at_utc`, `source`, `license`, `records` |
| source | `source_id:at-traditional-liquor`, `dataset_id:15048755`, `source_version`, 원 `evidence_kind`·`captured_at_utc`, `input_sha256`, `receipt_sha256`, `manifest_sha256`, `review_sha256`, `selection_sha256` |
| license | `label:portal-unrestricted-with-additional-notes`, `purpose:noncommercial_local_structured_display_and_fit`, `attribution:한국농수산식품유통공사(aT) 전통주정보`, 원 `source_url`, `raw_redistribution:false`, `source_media_included:false`, `free_text_included:false` |
| records | `catalog_record_id`, 원 `source_record_id`·`source_row_number`, 명시 `source_variant_group`, `facts`, `evidence{url,sha256}` |
| facts | `label`, `producer_name`, `source_category`, `category`, `abv_percent`, `volume_ml`, `gtin:null`, `taste_tags:null`, `aroma_tags:null`, `image_url:null`, `description:null` |

주종은 닫힌 대응표 `약주→약 · 청주`, `탁주→탁주`, `과실주→과실주`, `증류주→증류주`만
허용하고 원 `source_category`도 보존한다. 가격·available·업무 ID·expiry는 권위에 없다.
원 capture는 새 발행 시각으로 바꾸지 않는다. 파일 SHA로 pin한 버전은 검수 시점의 사실이며
상류 수정/철회 실시간 감지나 재고 보장이 아니다. 변경/권리 보류 시 해당 권위와 매핑을
재검수·교체해야 한다. `authored_regression_fixture`는 테스트용으로 끝까지 구분하며 실제
로컬 서비스 소비자는 원 receipt의 `operator_public_download_receipt`만 허용한다.

Backend는 별도 pin한 명시 업무 ID/그룹 매핑과 현재 DB의 라벨·주종·도수·용량을 대조한다.
현재 행/상태·시연 가격과 요청 간 snapshot 충돌 처리는 Backend 소유다. 가격은 항상 DEMO로
표시하고 기존 시연 bundle의 300초 만료나 false 권위 flag를 이 계약으로 변경하지 않는다.
발행은 새 ignored 디렉터리에서 입력을 다시 검증하고 완료 receipt에 정확 artifact SHA를 남긴다.
실패/기존 출력은 덮지 않으며 pinning은 서명이나 권리 검증 자체를 대체하지 않는다.

실제 기존 검수6행의 과실주2·약주2·증류주1·탁주1, 단일 도수/용량 사실을 새 권위로 발행했다.
원 20260731 CSV·획득 receipt/capture와 이전 manifest/review/실험은 보존하고 새 정책에 대한
로컬 재검수·selection의 해시만 추가했다. 새 수집·학습·독립 품질 개선 결과가 아니다.

## 데이터와 검수의 권리·역할

- 데이터 필드의 정본은 이미 허용된 [Wikidata CC0 구조화 snapshot](CATALOG-AUDIT.md)의
  라벨·P3962·P31·P2234·P2665다. [수집 receipt](WIKIDATA-COLLECTION.md)의 accepted·
  정확 ID/revision·raw/manifest 모델 해시와 원문10MiB 상한을 먼저 검증한다.
- 독립적인 first-party 상품 페이지는 사람이 같은 GTIN·용기·용량·도수를 교차 확인하는
  근거 URL·검수 메모로만 쓴다. 코드가 이 URL을 fetch하거나 외부 본문/이미지·맛/가격을
  수집하지 않는다. URL 모양과 일치하는 숫자가 그 페이지의 권위·권리·사실을 자동 증명하지 않는다.
- 2026-11-01 [Manitoba Liquor Mart의 상품 목록](https://www.liquormarts.ca/product/bavaria/500-ml-0)에서
  같은 식별자와 용기/용량/도수를 확인했다. [해당 약관](https://www.liquormarts.ca/retail-marketing/terms-and-conditions)은
  명시적인 공개 데이터셋 라이선스가 아니므로 이를 새 데이터/모델 원천으로 채택하지 않았다.
  [Royal Swinkels 공식 portfolio](https://royalswinkels.com/en/portfolio/beers-and-drinks/bavaria)는
  제품군 확인에 한정했고 [복사 제한](https://royalswinkels.com/en/legal-disclaimer)에 따라
  본문·사진을 데이터 파일/학습 입력으로 보관하지 않았다. 어느 사이트도 로그인/문의/폼·바코드 조회를 하지 않았다.
  검수 시각은 외부 페이지 수정일이 아니다. 외부 불변 snapshot/수정일은 확보하지 않았고 URL과
  확인 메모를 남긴 단계이므로 실시간 재고·현재 판매/포장 디자인·전체 변형의 동일성을 보증하지 않는다.
- 필드별 provenance에는 CC0 원천 ID/revision/URL/raw hash·property와 정규화 단위를 남긴다.
  변형 그룹과 식별 해석은 수동 명세의 선택이며 원천에 있던 관측값이나 완성된 상품군 분리라고
  표시하지 않는다. 가격·맛/향·제조사·묶음수·가용성을 추정하지 않는다.

## 입력 계약과 보류

P31 관계 자체의 명시 모순/unknown은 `instance_of_relations_require_review` 보류다.
정상 container 옆의 malformed brand를 제거해 혼합이 해결됐다고 간주하지 않으며,
`mixed_type_interpretation`도 이 보류를 덮을 수 없다. 확인된 brand/container 혼합에 대한
기존 한정 scope와 다른 경계다. [실제 전후 재현](measurements/2026-11-03-source-relation-integrity.md)을 따른다.

curation 명세는 `schema_version=1`, `algorithm=source-container-curation-v1`, 자료 성격,
raw/receipt/manifest **파일 해시**, 카탈로그 버전, UTC 검수 시각, QID별 선택을 가진다.
receipt 내부 manifest 해시는 기존처럼 검증 모델의 canonical 해시이며 파일 해시와 구분한다.
실제 명세는 ignored에만 보존하고, CI는 직접 작성한 가상 입력만 사용한다.

| 선택 필드 | 의미 |
|---|---|
| `catalog_record_id` | 사람이 부여한 고유 문자열 ID. QID/행 순서로 업무 ID를 만들지 않음 |
| `source_variant_group` | 변형이 학습/평가에 교차하지 않게 관리할 수동 그룹. 전체 변형 검수가 끝났다는 뜻은 아님 |
| `identity_scope` | `single_container_source_candidate`. 용기의 표현 단위이며 실제 판매 묶음수/거래 적격성은 별도 |
| `checked_facts` | 수동으로 고정한 exact GTIN·container class·mL·vol%. 이미 허용된 원천 값과 정확히 같아야 함 |
| `corroboration_url`·`corroboration_publisher`·`review_note` | 별도 HTTPS first-party 근거의 수동 검수 메모. feature/라이선스 원천으로 사용하지 않음 |
| `mixed_type_interpretation` | 브랜드/container 혼합이 있으면 필수인 한정 해석. 원래 P31/hold를 삭제하거나 수정하지 않음 |

처음에 snapshot 전체를 [포장 감사](PACKAGE-IDENTITY-AUDIT.md)로 다시 검사한다. 선택하지 않은
item의 qualified GTIN도 공유 식별자 충돌 검사에 포함한다. shared ID·알 수 없는 단위/수량·
문맥 있는 GTIN·미확인 라벨 등은 수동 메모로 덮을 수 없다. 같은 item에 명시 라벨·단일 GTIN·
용기·용량·도수 조합이 있는 경우에만 검수할 수 있고, 혼합 brand/container 해석만 별도의
수동 scope로 기록한다. 입력 변경·검수 사실 모순·미지정 item·중복 문자열 ID는 실패한다.

`backend_product_id` 등 업무 ID/가용성·외부 권리 승인 flag를 입력에 추가하는 것은 거절한다.
이번 CLI에는 업무 매핑·B0/B1 요청 내보내기·fit이 없다. 별도 [시연 export gate](BUSINESS-EXPORT.md)는
업무 snapshot·명시 검수 매핑을 소비한다. 이 source-only 출력을 자동 승격하지 않으며 실제
공개 원천의 실매핑·서비스 fit은 아직 미완료다.

## 출력과 실제 실행

```bash
uv run --locked python -m pubburi_recommendation.source_catalog \
  --manifest sources/wikidata-structured.json \
  --input .pubburi/source/entities.json \
  --receipt .pubburi/source/receipt.json \
  --curation .pubburi/catalog-curation.json \
  --output-dir .pubburi/source-catalog-new
```

- `source-catalog.json`: 선택한 원천 후보·필드 provenance·수동 해석·원래 P31/hold·미확인 값.
- `curation-report.json`: 원천/선택/미선택·그룹·해시·매핑/내보내기/fit 미완료 집계.
- `receipt.json`: 모든 파일 완성 뒤 `completed=true`. 중간 쓰기 실패의 일부 파일은
  `completed=false`로 남으며 소비/완료 처리하면 안 된다. 기존 디렉터리는 덮지 않는다.

2026-11-01의 실제 검수는 이전 accepted4항목·같은 revision/raw를 재사용했고 추가 GET은0이다.
독립 사실 명세와 일치하는 **원천 포장 후보1/4**를 명시 선택해1개 그룹으로 관리했다.
원래 감사의 수동 보류4/4와 그중 혼합 분류1개는 보존하며, 새로운 scope를 원천 데이터 수정이나
기존4항목의 SKU 승인으로 표현하지 않는다. 제조사/묶음수·맛/향·시연 가격 등은 채우지 않았다.
원문 SHA256은 `b6dc9768ade08b7c166ab4c57899f4af871cf7a984140266b680e0cea5d636f1`다.

서비스 SKU·Backend 매핑·B0/B1 wire export·서비스 fit 승격은 모두0이다. 한정된 실제 자료의
포장 식별/정보 보존 결과이며 학습·추천 관련성·사람의 만족도·성능 개선 결과가 아니다.
그룹1개만으로 일반화/차원 축소 실험을 억지로 추가하지 않았고 Recall/NDCG를 계산하지 않았다.
독립 사실 명세는 모델 점수 함수·UI/행동 데이터와 분리해 고정했으며 실제 원본/명세/출력은 ignored,
공개 근거는 구현·자체 fixture와 집계/한계다.

이 source-only 단계 뒤 [명시 업무 매핑과 실제 fit1개](REVIEWED-CATALOG-FIT.md)를 별도로
실행했다. source-only 후보/원래 보류와 업무DEMO 연결·known-catalog fit의 완료 조건을 구분한다.

[구현](../src/pubburi_recommendation/source_catalog.py) ·
[회귀](../tests/test_source_catalog.py) ·
[작업/검증](https://github.com/Pubburi/Recommendation/blob/39647aab11e2bb212a23162ad1c57596860b32a7/docs/plans/2026-11-01-reviewed-source-catalog.md)
