# 포장 문맥별 용량 관측

`python -m pubburi_recommendation.volume_context`는 검수한 상품군의 **P2234 용량 statement +
P518 applies-to-part 문맥**을 별도 관측으로 보존한다. 상품군의 단일 용량을 결정하거나 판매 SKU를
만드는 도구가 아니다. 같은 상품군의 캔 330mL와 케그 20L를 평균 내거나 첫 값으로 덮어쓰지 않는다.

[P518 공식 정의](https://www.wikidata.org/wiki/Property:P518)는 주장이 적용되는 부분·측면·형태를
나타낸다. 모든 P518이 포장이거나 모든 문맥 개체가 완성 상품이라는 뜻은 아니다. 검수자는 별도로
고정 수집한 정의의 ID·revision·라벨과 `volume_context_only` 범위를 명시한다. 구조화 사실은
[Wikidata CC0 범위](https://www.wikidata.org/wiki/Wikidata:Licensing)에 한정하며 이미지·외부 본문·
맛·가격·상품 인증을 포함하지 않는다.

## 입력과 원천 권한

입력 파일은 모두 직접 제공한다. CLI는 네트워크·DB·모델을 사용하지 않는다.

- `--manifest`: 검수한 CC0 구조화 원천 명세.
- `--input`, `--receipt`, `--review`: 상품군 snapshot·수집 영수증·명시 product_family 검수.
- `--context-input`, `--context-receipt`: 문맥 정의 snapshot·수집 영수증.
- `--spec`: 코드/정제 실행 전에 고정한 사실·검수 범위.
- `--output`: 새 ignored `.pubburi` 경로. 완성 보고서를 원자적으로 발행하고 기존 파일은 덮어쓰지 않는다.

`spec`의 schema_version은1이다. 각 입력의 SHA-256, manifest SHA-256, selected family_groups·
source_revisions, contexts의 revision/label/scope/rationale, statement ID별 expected_observations를
필수로 받는다. 기대 사실은 `source_record_id`, `context_id`, `volume_ml`의 정확한 값 또는 null이다.
용량은 부동소수 오차/묵시적 반올림을 피하기 위해 정규화한 **십진 문자열 mL**로 보존한다.
아직 허용하지 않은 family/context·statement가 기대 명세에 들어가거나 실제 관측과 다르면 실패한다.

원천 두 개의 영수증을 각각 끝까지 검증한다. accepted 상태·허용 라이선스·manifest 모델 해시·
정확 요청 ID·양의 revision·원문 해시를 확인하고 원천을 합친 가짜 영수증을 만들지 않는다.
문맥 검수는 정의의 라벨/revision과 일치해야 하고, 상품군은 명시 검수된 product_family이며 기존
scalar volume이 unknown이어야 한다. evidence_kind는 검수자의 선언이고 collection_modes의
live_get/offline_replay와 함께 보존한다. offline 형식 검증은 새 외부 사실 수집·권리 승인이 아니다.

```bash
uv run --locked python -m pubburi_recommendation.volume_context \
  --manifest sources/wikidata-structured.json \
  --input .pubburi/families/entities.json --receipt .pubburi/families/receipt.json \
  --review .pubburi/families/review.json \
  --context-input .pubburi/contexts/entities.json --context-receipt .pubburi/contexts/receipt.json \
  --spec .pubburi/observations/frozen-spec.json \
  --output .pubburi/observations/report.json
```

## 수량과 문맥의 경계

정상/선호 rank·P2234 property·quantity datatype/value·명시 amount를 요구한다. mL/L/cL의
정확한 `http(s)://www.wikidata.org/entity/…` 단위 URI만 변환한다. 유한·양수·최대1,000,000mL,
서로 같은 양끝 범위·지원 정밀도를 확인한다. 0/음수/무한/범위·단위 namespace 오인·반올림은
unknown과 보류 이유로 남긴다. 이 도구의 더 엄격한 statement 해석은 기존 family scalar 정규화를
변경하지 않는다.

qualifier는 P518 **하나의 item snak**만 허용한다. 명시 property/datatype/type·ID/numeric-id·
entity-type와 검수 정의를 대조한다. 다른 qualifier·중복/여러 문맥·잘못된 qualifiers-order는 보류한다.
한 family/context의 여러 statement는 동일량이어도 모두 보류하며 삭제·평균·덮어쓰기를 하지 않는다.
statement 순서는 결과에 영향을 주지 않는다. deprecated는 활성 관측에서 제외하고, 누락·중복·
다른 원천의 statement ID는 실패한다. 선택 최대10상품군·10정의·상품군당100 claim이며 파일별
10MiB 상한은 공통 JSON 경계가 적용한다.

출력은 statement별 source ID/revision/URL·family_group·문맥 ID/revision/라벨·volume_ml·
reference 개수·hold_reasons를 보존한다. **보류가 있는 관측은 검수 완료된 변형 후보가 아니다.**
references의 개수는 내용의 정확성/독립 확인을 보증하지 않는다. 가족 단위 volume_ml은 계속 null,
ABV·GTIN·Backend ID도 null이다. family_group을 다음 데이터 분리에도 그대로 사용해야 하며,
서로 다른 문맥을 다른 학습/평가 군으로 나누어 누수를 만들면 안 된다.

## 실제 적용과 다음 단계

2026-11-01 UTC에 기존 검수된6상품군의11활성 P2234 statement와, 고정 GET1회의 문맥 정의4개를
결합했다. 코드 전 수동 기대는330mL5개·20,000mL5개·750mL1개였고 모두 개별 관측으로 보존했다.
가족 단일 용량은6/6 unknown을 유지했다. 정의의 라벨은 beer can/keg/Champagne bottle/Steinie
beer bottles이며 완성 포장/SKU 승인을 뜻하지 않는다. 기존 snapshot의 scalar 출력이11값을
누락시킨 버그라고 해석하지 않는다. 가족 grain에서 unknown인 것이 맞고 새 관측 grain이 정보를
추가로 보존한다. 이는 지연/추천 품질/사람의 만족도 개선 수치가 아니다.

이번 신규 Backend 매핑0·모델 fit0이다. 기존 단일 source-backed 업무 DEMO와 분리한다. 다음에는
허용 원천의 개별 포장 정체성·추가 필수 필드/GTIN·명시 업무 매핑을 검수한 뒤 기존
[source curation](SOURCE-CATALOG.md)과 [업무 export](BUSINESS-EXPORT.md) 계약을 적용한다.
이 관측만으로 엄격한 기존 gate를 완화하거나 ABV/제조사/pack count/가격을 추정하지 않는다.
[계획과 재현 근거](plans/2026-11-02-volume-context.md)에 동결·실제 결과·한계를 기록한다.
