# 구조화 원천의 포장 식별 감사

`python -m pubburi_recommendation.package_identity_audit`는 허용된 Wikidata snapshot에서
GTIN·포장 종류·용량·도수·정체성의 근거를 분리한다. 원천 조회 성공이나 바코드 검증 숫자 통과를
판매 SKU 승인으로 바꾸지 않는다. Backend 등록·상품 ID 부여·학습·HTTP 추천은 수행하지 않는다.

## 원천과 허용 범위

2026-11-01 [Wikidata 라이선스](https://www.wikidata.org/wiki/Wikidata:Licensing)와
[공식 SPARQL 서비스](https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service)를 확인했다.
이번 처리는 CC0 구조화 claim의 P3962(GTIN), P31(분류), P1716(브랜드), P176(제조사),
P2665(도수), P2234(용량), 라벨과 revision에 한정한다. 기존 manifest의 구조화 정규화 범위를
사용하며 이미지·설명 본문·외부 리뷰나 링크 원문까지 CC0라고 간주하지 않는다. 원본 재배포나
외부 상점 수집은 하지 않았고 가격·판매 상태·맛·향·묶음수는 추론하지 않는다.

소량 발견 질의는 공식 WDQS에 `P3962`와 양수 `P2665`가 있는 item을 `LIMIT 10`으로 한 번
GET했다. 별도의 bounded probe로 timeout20초·응답1MiB 상한·redirect 금지를 적용하고 원문,
query/응답 해시와 receipt를 ignored에 보존했다. 발견 질의는 versioned 수집기가 아니므로
그 응답을 정제 입력으로 직접 사용하지 않는다. 얻은 ID4개만 기존 [고정 수집기](WIKIDATA-COLLECTION.md)의
maxlag5·최대10ID·본문/전송 오류·revision/정확 ID·실패 receipt 검사를 거쳐 다시 확보했다.
실행 시 두 GET 모두 성공했으며 자동 재시도·외부 GTIN 조회·계정/키·이미지 수집은 없었다.

## 검증과 보류

| 경계 | 처리 |
|---|---|
| snapshot | accepted receipt의 모드/HTTP·CC0·원문/manifest 모델 해시·요청 ID와 revision을 확인한다. 실패/변경 원문은 사용하지 않는다. 상품군 표현 실험과 같은 경량 gate를 재사용한다. |
| GTIN 문자열 | ASCII 숫자8/12/13/14자리만 받으며 trim·정수 변환으로 원문을 바꾸지 않는다. 마지막 숫자를 제외하고 오른쪽부터3/1 가중치를 적용해 mod10 검증한다. all-zero는 수학적 통과와 별개로 사용하지 않는다. |
| 중복 비교 | 선행0을 보존하고14자리0-padding 비교 키를 별도로 만든다. 새 GTIN 발급/포맷 지정이 아니며, 서로 다른 item이 같은 키를 쓰면 보류한다. |
| claim 문맥 | deprecated GTIN은 제외하고 수를 기록한다. qualifier·알 수 없는 값/타입·비정상 rank·다중 식별자는 자동 확정하지 않는다. source reference 개수는 근거 링크의 존재 수이며 진실성 점수가 아니다. |
| 수치/포장 | quantity 타입과 normal/preferred rank, value snak 및 문맥을 확인한다. 검수 단위의 `http(s)://www.wikidata.org/entity/` URI만 허용하며 bare QID·외부 호스트의 같은 suffix를 단위로 해석하지 않는다. L→mL와 vol%는 지원하지만 일반 percent를 vol%로 대체하지 않는다. 다중/범위/문맥·미지원 단위는 unknown이다. 이름의 `500`이나 이미지로 포장을 채우지 않는다. 현재 검수한 container class는 [beverage can](https://www.wikidata.org/wiki/Q1121690)뿐이다. |
| grain | 같은 item에 명시 용기·단일 GTIN·라벨·용량·도수가 있는지와 브랜드/container 혼합을 따로 표시한다. 같은 item의 필드 조합도 개별 변형·묶음수를 확정하지 않는다. |
| 수동 검수 | raw/receipt 해시와 정확한 revision URL에 결속한다. `hold` 또는 `candidate_for_manual_mapping`만 기록한다. 후보 판단도 Backend 매핑·SKU 승인·fit 적격성을 만들지 않는다. 소스 보류 사유를 수동 후보로 덮을 수 없다. |

[GS1 US GTIN 설명](https://www.gs1us.org/upcs-barcodes-prefixes/what-is-a-gtin)과
[검증 숫자 설명](https://www.gs1us.org/tools/check-digit-calculator),
[GS1 General Specifications 25.0의7.9.1](https://documents.gs1us.org/adobe/assets/deliver/urn%3Aaaid%3Aaem%3Aafbf55ad-0151-4a0c-8454-d494c0dc9527/GS1-General-Specifications.pdf)을
알고리즘 근거로 사용했다. checksum은 문자열 오류 검사다. GS1의 실제 할당·진위·합법/안전 판매,
현재 Backend 상품과의 동일성을 검증하지 않는다. 공식 바코드 조회/신청 폼을 사용하지 않았다.
수량 구조/단위 URI는 [공식 Wikibase JSON](https://doc.wikimedia.org/Wikibase/master/php/docs_topics_json.html)을
참고했다. 기존 정규화의 허용적인 rank/type/URI suffix 처리는 포장 식별 승인의 근거로 충분하지
않으므로 새 감사에 더 엄격한 gate를 두며 기존 상품군/HTTP 모델의 계약은 변경하지 않았다.

## 실제 소량 관측

2026-11-01 05:44:49 UTC의 accepted GET은4항목·39,892B다. 이번 ID4개 중 신규3개와
이전 브랜드 표본1개를 구분한다. 발견 질의는561B/4ID이며 요청 시각 필드가 없으므로 정확한
시각을 추정하지 않는다. 목적 표본이어서 Wikidata 전체 주류의 충실도 추정에 사용하지 않는다.

| 관측 | 분자/분모 |
|---|---|
| active GTIN·검증 숫자 통과 | 각4/4 claim |
| item 내부의 단일 문맥 없는 식별자 | 4/4 item |
| 명시 용기+라벨+GTIN+관측 용량/도수의 조합 | 1/4 item |
| 브랜드/container 분류 혼합 | 1/4 item (위 조합의 같은 item) |
| 명시 용기 미확인·용량 unknown | 각각3/4 item |
| 라벨 unknown·도수 unknown | 각각1/4 item |
| GTIN source reference 없음 | 4/4 claim |
| canonical 식별자 공유 | 0개 그룹 (이4항목 범위) |
| 해시 결속 수동 보류 | 4/4 item |
| 승인 Backend 매핑·fit 승격 | 각각0 |

1개에서 관측한0.5L→500mL·5vol%·beverage can은 정보로 보존했다. 동시에 브랜드 분류가
있어 포장/변형의 grain을 확정하지 않았다. 제조사·묶음수 부재는 별도 unknown이며 전체
파이프라인 중단의 이유로 삼거나 추정값으로 보완하지 않았다. 후속으로 독립 근거에서 개별
포장과 변형을 검수하고, Backend 업무 상품이 존재할 때만 명시 매핑을 합의해야 한다.

실행 원문 SHA256은 `b6dc9768ade08b7c166ab4c57899f4af871cf7a984140266b680e0cea5d636f1`,
수집 receipt SHA256은 `dc125c18a0ede37e622bce423dbfc875aabf0a37e335d54c9653a972d76fe82b`다.
raw/개별 카탈로그·검수/결과는 ignored에만 보존한다. 이번 결과는 데이터 식별 증가분이며 서비스
카탈로그 준비·서비스 B1 fit·추천 관련성/사람의 만족도나 속도 개선의 성과가 아니다.

## 로컬 실행

```bash
uv run --locked python -m pubburi_recommendation.package_identity_audit \
  --manifest sources/wikidata-structured.json \
  --input .pubburi/source/entities.json \
  --receipt .pubburi/source/receipt.json \
  --review .pubburi/package-review.json \
  --evidence-kind reviewed_public_source \
  --output-dir .pubburi/package-audit-new
```

`--review`는 선택이며 생략하면 `not_performed`다. 자체 입력에는
`--evidence-kind authored_regression_fixture`를 사용한다. review는 `input_sha256`,
`receipt_sha256`, QID별 `decision`·정확한 `evidence_url`·`rationale`을 가진다.
수집 manifest/JSON 상한과 권리 gate를 먼저 확인하고 새 ignored 디렉터리만 만든다.
`package-records.json`, `audit-report.json`, receipt를 보존하며 마지막 receipt의
`completed=true`는 감사 파일 완성을 뜻한다. 일부 쓰기 실패의 `completed=false`나 exit2,
기존 경로를 새 성공으로 덮지 않는다. 출력의 `algorithm=package-identity-audit-v1`과 실행 코드
커밋도 함께 기록하고 raw가 같아도 변경된 projection을 검수 완료로 자동 간주하지 않는다.

[핵심 구현](../src/pubburi_recommendation/package_identity_audit.py) ·
[receipt 공통 gate](../src/pubburi_recommendation/collection_snapshot.py) ·
[직접 작성한 회귀](../tests/test_package_identity_audit.py) ·
[작업/검증](plans/2026-11-01-package-identity-audit.md)
