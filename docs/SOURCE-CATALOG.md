# 검수한 원천 포장 카탈로그

`python -m pubburi_recommendation.source_catalog`는 허용된 구조화 원천과 별도의 수동 검수
명세를 읽어 **포장 후보의 원천 카탈로그**를 만든다. 브랜드/용기 분류가 섞인 원천을 그대로
업무 SKU로 등록하지 않고, 이번에 해석한 단위·근거와 원래 충돌을 함께 남긴다.
문자열 `catalog_record_id`·`source_variant_group`은 Backend ID나 판매 적격성 승인이 아니다.

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

[구현](../src/pubburi_recommendation/source_catalog.py) ·
[회귀](../tests/test_source_catalog.py) ·
[작업/검증](plans/2026-11-01-reviewed-source-catalog.md)
