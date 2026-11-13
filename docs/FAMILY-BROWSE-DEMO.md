# 검수 상품군의 별도 오프라인 browse DEMO

`python -m pubburi_recommendation.family_browse_catalog`는 허용 CC0 상품군과 개별 검수한 aT
named-product 행을 **reviewed_source_family_browse_demo_only** authority로 검수한다. 기존 포장
카탈로그의 GTIN/container/known-volume 조건을 완화하지 않는다. 상품군은 물리 포장/SKU·
판매·재고의 증거가 아니며 이 결과를 일반 서비스 카탈로그로 자동 승격하지 않는다.

## 권리·단위와 입력

[Wikidata 구조화 데이터의 CC0](https://www.wikidata.org/wiki/Wikidata:Licensing)는 라벨과
claims에만 적용한다. 외부 본문·사진·후기·맛/향은 포함하지 않는다. 기존 accepted receipt와
raw/manifest/review 파일 해시·정확 revision, 검수 product_family 종류를 다시 확인한다.
curation의 exact 라벨/언어·P31/P176·실제 vol%와 일치해야 하며 다른 kind·모순 관계·단위/
수치 unknown·미래 검수·변경 권위는 거절한다. missing ABV를0으로 채우지 않는다.

curation algorithm은 `reviewed-source-family-browse-demo-v1`이고 선택은 최대10개다.
각 선택의 `catalog_record_id`와 `source_variant_group`을 고유하게 선언하고 identity_scope는
위 family-browse scope로 고정한다. checked_facts는 source_revision·label·label_language·
정렬/중복 없는 instance_of_ids/producer_ids·known abv_percent·volume_ml=null이다.
상품군의 미확인 용량·맛/향·포장/묶음수·GTIN 할당·가격/가용성은 unknown으로 남긴다.
기술 `sku_group`에 전달하는 문자열도 이 수동 상품군 그룹이며 SKU 정체성 증명이 아니다.

aT 분기는 기존 [사실 전용 입력](CATALOG-AUDIT.md)의 CP949 CSV·영수증·행별 검수·동일 제공자
근거를 재사용한다. 별도 curation algorithm은 `reviewed-at-named-browse-demo-v1`이며,
선택 key는 원문 SHA256과 행번호를 포함한 `at:15048755:<sha256>:row:<n>`이다.
checked_facts는 source_row_number·source_version·label·producer_name·category·known
abv_percent·volume_ml=null을 원래 검수 결과와 대조한다. QID/P31/P176/revision이나
product_family 종류를 만들지 않고 provenance에 실제 `named_csv_product_record_not_verified_sku`
grain을 남긴다. `catalog_record_id=at-browse-<version>-row<n>`과 고유 기술 그룹을 결속하며,
미검수/중복 행·다른 원문/검수 해시·미래 검수·fixture를 실제 원천으로 바꾸는 선언은 거절한다.
근거 종류와 해시는 감사에서 검증한 같은 receipt 스냅샷을 사용한다.
`fact_evidence_files`는 curation과 같은 폴더의 근거 원문 파일명만 받으며 원래 검수 해시를
재확인한다. URL을 가져오거나 이름만으로 다른 원천과 자동 결합하지 않는다.

아래 명령과 후속 `--family-review` 인자는 그대로 쓰되 aT manifest/CSV/영수증·원래 행 검수·
별도 browse curation을 전달한다. 기본 aT 감사 출력만으로 업무 export를 승인하지 않는다.

```bash
uv run --locked python -m pubburi_recommendation.family_browse_catalog \
  --manifest sources/wikidata-structured.json \
  --input .pubburi/source/entities.json --receipt .pubburi/source/receipt.json \
  --review .pubburi/family-review.json --curation .pubburi/family-curation.json \
  --output-dir .pubburi/family-browse-catalog-new
```

새 private 디렉터리에 source-catalog/curation-report/완료 receipt를 쓴다. 기존 출력은
읽기/재계산 전에 보존하며 실패를 완료로 표시하지 않는다. 원문·검수·모델은 Git에 넣지 않는다.

## 명시 업무 매핑과 기존 fit 재사용

기존 [business export](BUSINESS-EXPORT.md)와 [reviewed fit](REVIEWED-CATALOG-FIT.md)에
`--family-review <원래 검수 파일>`을 명시하면 새 authority loader를 선택한다. 생략하거나
container 명세에 섞으면 실패한다. 기존 포장 loader/정체성 gate는 그대로 유지한다.

- 실제 허용 원천에는 `snapshot_origin=owned_family_browse_demo`·`capture_method=http_read`의
  **root 소유 전용 폐기 업무 DEMO/API**만 허용한다. 기존 existing_local_catalog/판매·서비스
  origin은 사용할 수 없다. CI authored 원천만 demo_fixture/authored로 별도 검증한다.
  origin/scope는 수집자의 명시 기록이며 CLI가 root/DB 소유를 인증하는 것은 아니다.
  실제 소유·행 생성/HTTP 읽기 근거는 별도로 보존한다.
- Product7/features8 계약은 유지한다. 상품군과 원래 라벨/도수가 정확히 같아야 하며 volumeMl·
  description·tasteTags·aromaTags는 null이다. sourceName/URL/메모가 권리를 승인하지 않는다.
  aT의 검수 주종도 원래 Product7 응답의 type과 정확히 같아야 하며 자동 정규화로 맞추지 않는다.
- 모든 선택을 서로 다른 실제 API 반환 업무 ID에 명시 매핑한다. eligibility_scope도 family
  browse scope로 고정하고 검수 그룹·전체 parsed 응답/snapshot 해시·시각을 결속한다.
  무매핑/부분 매핑·scope 혼합은 export를 거절하며 이름/QID로 업무 ID를 만들지 않는다.
- family-only에서만 원천/업무 양쪽 volume=null을 보존한다. 포장 카탈로그의 known volume
  조건은 바뀌지 않는다. 원문과 다른 ABV·수량 보충·빈 태그로 unknown 대체도 거절한다.
- 업무 분류·가격·공개 탐색 가용성은 명시 DEMO 권위다. 시세/실판매 관측이 아니며 실제
  재고·주문 적격성을 뜻하지 않는다. 전체 응답 hash/60초 캡처·5분 freshness는 서버 revision/
  원자적 읽기 보장이 아니다. 기존 stale/future·변경 응답 거절을 유지한다.

fit 전에 원천 catalog hash·명시 업무 사실·독립 후보/조건/fallback 명세를 고정한다.
기존 B1과 B0/독립 검사기를 그대로 실행하며 family 결과의 fit_scope는
`known_mapped_family_browse_demo`다. 데이터 scope와 physical_sku_or_service_catalog_approved=false를
남긴다. 다중 수치 범위가 활성화돼도 사용자 선호 학습/관련성·holdout 일반화·서비스 품질이나
전체 AI03 완료가 아니다. 기존 container DEMO1·source11 상품군 실험과 합산하지 않는다.

## 실행된 데이터 범위

| 원천·적용 단위 | 실제 검수·실행과 한계 |
|---|---|
| 기존 accepted6 중 known-ABV5상품군 | 별도 업무 DEMO 명시 매핑·14개 고정 사실 재현. 신규 수집/SKU5개가 아님. [원값/분모](https://github.com/Pubburi/Recommendation/blob/3f0a6cfb0780d06fda06ad4e6920f814e5f6a798/docs/measurements/2026-11-03-family-browse-demo.md) |
| 다른 기존 accepted4 중 상품군1 | 정확5.2vol%·정상 P31/P176 검수, 두 소유 DB에서 같은12조건 각각 통과·모델/전체 결과 동일. 같은1상품군/12조건 반복이며2상품/24개 독립 정답이 아님. 나머지3항목 보류·GTIN/포장 gate 유지 |
| 새 CC0 수집3 중 상품군1 | 새로 고정한3ID의 단일 공식 GET이 accepted=true. Duchesse de Bourgogne의 정상 P31/P176·6.2vol%·revision을 검수해 소유 PG의 실제 API 반환 ID에 명시 매핑. 기존 export/bundle/B1·B0로 사전 고정12조건 통과하고 실제 Backend의 PROVIDER/family DEMO·BASELINE 경로도 확인. 나머지는 beer brand grain1·조건부 제조사 진술1로 보류 |
| aT 검수 named-product 행2 | 기존 20260731 CSV의 개별 검수 사실을 소유 폐기 PG의 실제 API 반환 두 ID에 명시 매핑했다. 기존 export·fresh checked bundle과 B1/B0 고정12조건을 검증했다. 주종1어휘/IDF1, 도수6.5–8.5 활성, 용량·맛/향 관측0이며 가격은 별도 업무 DEMO 값이다. 상품군·SKU 수에 합산하거나 일반 서비스 채택으로 세지 않는다 |

두 단일 상품군 카탈로그는 각각1상품군/1그룹·업무 주종1어휘/IDF1이고, known 도수는 관측1의
상수라 비활성이다. P2234 부재의 용량은 관측0/누락1, 맛/향은 각각null1이며0/빈 배열로
채우지 않았다. 맥주·2000원·가용성·이미지 placeholder는 명시 업무 DEMO 권위다. 독립 관련성
정답이 없어 순위 지표는 미산출이며, 기존5·다른1·새1과 source11/container DEMO1을 합산하지 않는다.

이전 와인/시드르6후보의 원문 GET은 api_maxlag/accepted=false로 중단했고 재시도·한도 완화·
endpoint 우회0이다. 그 실패의 신규 수집0과 이번 별도3ID의 성공을 구분한다. 옛0ID·제조사429·
aT의 당시 다운로드 보류 이력도 보존한다. 이후 별도로 승인·획득한 aT 사실 입력과 혼동하지 않는다.

Backend의 기본 container 소비 경계는 유지하며, 명시 family browse opt-in·family/DEMO 표시·
unknown 용량·현재 본인 취향/업무 재검증과 React 홈의 추천/이유 요청은 검수 DEMO 범위에서
연결했다. 일반 서비스 카탈로그 채택·R02/R04/AI03 최종 인수는 남아 있다. 판매·장바구니 SKU로
자동 승격하지 않는다. 원문/응답·실제 ID·명세·모델·로그는 ignored에 두며 재현 명령은 위 정제와
[business export](BUSINESS-EXPORT.md)·[reviewed fit](REVIEWED-CATALOG-FIT.md)의 명령을 따른다.
