# 기존 허용 상품군의 신규 정제·업무 DEMO 적용

기준 main `1d7fbde`의 기존 도구와 Python3.12.14·잠금 sklearn1.9.1을 사용했다.
2026-11-01에 accepted된 CC0 원문4항목에서, 아직 업무 browse에 적용하지 않은 명명
상품군1개를 새 hash-bound 검수·정제 권위로 선택했다. 새 모델/특성/제공자/loader는 만들지
않았다. 원문·검수·실제 업무 응답/ID·명세·모델·로그는 ignored에만 보존한다.

## 원천 선택과 수집 상태

[Wikidata 구조화 CC0](https://www.wikidata.org/wiki/Wikidata:Licensing)와
[접근 조건](https://www.wikidata.org/wiki/Help:Data_access)을 다시 확인했다. 원문 revision의
라벨/언어·정상 unqualified P31/P176·정확 vol% 도수5.2를 수동 검수했다. P2234가 없어 용량은
unknown이다. 원문 GTIN 문자열은 포장·할당 증명이 아니며 family 권위에는 전달하지 않는다.
이름으로 용량·맛/향·포장이나 SKU를 만들지 않았다. 다른3항목의 라벨/도수 단위·brand/container
보류는 이 선택으로 해제하지 않았다.

별도로 맥주 외 와인/시드르의 명시 제조자·도수 사실을 찾는 새 목적을 먼저 고정했다.
공식 SPARQL GET1회는 HTTP200·804B·6후보였지만, 기존 수집기의 Action GET1회는
HTTP200·478B의 `api_maxlag`였다. accepted=false 영수증을 보존하고 재시도·maxlag 완화·
다른 endpoint 우회 없이 중단했다. **신규 live 수집 성공0, 기존 허용 원천의 새 적용1**이다.
기존 ABV=0/GTIN/can/양수 용량의0ID 결과·제조사429·aT 수집 보류를 바꾸지 않았다.

## 실제 적용과 관측

root 소유의 두 별도 업무 DB에서 원래 관리 API로 추가한 동일한 상품군 시연 행을 공개 GET으로
각각 읽었다. 분류 맥주·가격2000원·탐색 가용성·이미지 placeholder는 명시 업무 DEMO 권위다.
원천 판매가/재고/사진 관측이 아니다. 두 snapshot 모두 `owned_family_browse_demo/http_read`이며
각 실제 API 반환 ID를 별도 명시 mapping·전체 응답/snapshot hash에 결속했다. 시각만 갱신한
snapshot을 쓰지 않았고, 원래 freshness 안에서 export와 fit을 실행했다.

| 범위·관측 | 값과 해석 |
|---|---|
| 새 정제 선택 | 기존 accepted4항목 중 product_family1. 신규 수집 성공0 |
| 실제 mapping/export | 두 DB 각각1행, B0/B1 각각1행. 같은 상품군의 반복이며2상품이 아님 |
| scope | reviewed_source_family_browse_demo_only / known_mapped_family_browse_demo |
| 기존 B1 fit | 각1상품군/1수동 그룹, category:맥주1어휘·IDF1.0 |
| ABV | 관측1/누락0, min=max5.2vol%. 알려진 상수라 수치 거리 비활성 |
| 용량 | 관측0/누락1, null 보존·거리 비활성 |
| 맛/향 | 각각null1/1, 검수 빈 태그0/1 |
| 독립 사실·제약 | 사전 고정12조건을 각 DB에서12/12 통과. 24개 독립 시나리오가 아님 |
| 재현 비교 | fit 요약·어휘/IDF·모델 지문·12개 case 전체 결과·관련성 미산출 상태 동일 |
| 관련성/일반화 | 독립 관련성 정답 없음으로 순위 지표 미산출. 사용자·holdout 품질 평가 없음 |

명세는 업무 snapshot 검증/fit 전인 2026-11-04 11:28:55 UTC에 고정했고 실행은11:31:27–11:31:29 UTC였다.
cold·명시 주종·ABV5.2의 정확 경계/양쪽 바깥 제외·DEMO가격 경계/미달 제외·다른 hard주종·
명시 제외·known 상수ABV와 unknown 용량/맛의 fallback을 scorer/필터에서 정답을 만들지 않고
선언했다. B0/B1은 같은 후보/조건으로 대조했다. 실행/캡처 시각과 snapshot/mapping hash는
각 DB에서 다르며 전체 보고서의 byte 동일성을 주장하지 않는다.

## 재현 경로

[정제 loader](../../src/pubburi_recommendation/family_browse_catalog.py),
[업무 export](../../src/pubburi_recommendation/business_export.py),
[기존 fit·독립 검사](../../src/pubburi_recommendation/reviewed_catalog_fit.py)를 그대로 사용한다.
아래는 ignored 입력을 준비한 운영자용 명령 형태다. 원문 accepted receipt/revision·새 검수/
curation·명시 mapping·동결 사실 명세의 hash는 별도 ignored 인계에 결속한다. 실제 재실행에는
새로 읽은 소유 업무 snapshot과 그 응답에 결속한 mapping이 필요하며 시각만 바꾸지 않는다.

```bash
uv run --locked python -m pubburi_recommendation.business_export \
  --manifest sources/wikidata-structured.json \
  --input .pubburi/source/entities.json --source-receipt .pubburi/source/receipt.json \
  --curation .pubburi/family-curation.json --family-review .pubburi/family-review.json \
  --business-snapshot .pubburi/current-business-snapshot.json \
  --mapping .pubburi/explicit-mapping.json --output-dir .pubburi/family-export-new

uv run --locked python -m pubburi_recommendation.reviewed_catalog_fit \
  --manifest sources/wikidata-structured.json \
  --input .pubburi/source/entities.json --source-receipt .pubburi/source/receipt.json \
  --curation .pubburi/family-curation.json --family-review .pubburi/family-review.json \
  --business-snapshot .pubburi/current-business-snapshot.json \
  --mapping .pubburi/explicit-mapping.json --spec .pubburi/frozen-fit-spec.json \
  --output-dir .pubburi/family-fit-new
```

## MVP 기여와 남은 경계

DAT02/DAT04의 실제 원천 정제·명시 업무 매핑·기존 B1 적용을1상품군만큼 진행했다. 기존
source11·container DEMO1·family DEMO5·authored3은 각각의 grain/보고서 그대로 보존하며
숫자를 더해 서비스 SKU/데이터 품질 성과로 쓰지 않는다. 단일 후보·상수/미확인 수치로 순위
개선이나 충분한 서비스 카탈로그를 주장할 수 없다. 원래 소스/테스트/스크립트/의존성95파일과
기존 API/core/보고서·README20파일의 hash는 실행 전후 그대로다.

현재 Backend의 첫 B1 소비자는 container-only이며 이 family scope를 계속 거절한다.
R02의 다음 선행 계약은 별도 browse 목적에서 family scope·volume=null·DEMO 권위와
`service_catalog_approved=false`를 명시 수용하고 현재 업무 사실을 재검증하는 것이다.
일반 container bundle에 섞거나 판매/장바구니 SKU로 자동 승격하지 않는다. 이 소비 계약의
공동 결정·Backend/React 연결과 충분한 허용 현재 카탈로그/독립 평가는 남았으며 전체
R02/R04/AI03·20MVP 기능 완료 수를 올리지 않는다. 사용자/미래 로그를 기다리지 않는다.
