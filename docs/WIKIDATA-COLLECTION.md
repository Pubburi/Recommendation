# 제한된 Wikidata 수집·오프라인 재생

`wikidata_collect`는 공식 endpoint에서 명시 QID를 한 번 조회하고, 검증한 원문·허용 필드 projection·
수집 영수증을 새 ignored 디렉터리에 보존한다. 기존 수동 원문 준비와 오프라인 `catalog_audit` 사이의
수집 경계를 구현했다. 서버 시작·health/B0/B1 실행은 이 도구나 네트워크에 의존하지 않는다.

## 원천·필드의 권리와 단위

2026-11-01에 [Wikidata Licensing](https://www.wikidata.org/wiki/Wikidata:Licensing),
[Data access](https://www.wikidata.org/wiki/Wikidata:Data_access),
[공식 wbgetentities 명세](https://www.wikidata.org/w/api.php?action=help&modules=wbgetentities),
[API etiquette](https://www.mediawiki.org/wiki/API:Etiquette)를 확인했다. 구조화 item은 CC0이며
사이트 본문·연결 사진·다른 사이트의 권리로 확대하지 않는다. SourceManifest는 이 검수 결정을
기록하며 데이터의 사실 정확성·개별 SKU·학습 품질을 승인하는 장치가 아니다.

| projection | 출처·처리 | 검수 경계 |
|---|---|---|
| label | item의 ko/en 라벨 | 원문 본문/설명 문장을 수집 특성으로 쓰지 않음 |
| instance_of_ids | P31의 item ID | Backend 주종이나 개별 판매 SKU로 자동 매핑하지 않음 |
| producer_ids | P176의 item ID | 브랜드·생산자·상품군의 정체성을 별도 검수 |
| abv_percent | P2665·volume-percent 단위 | 0–100, 불명확 단위/범위/문맥/다중값은 unknown |
| volume_ml | P2234의 mL/L/cL | 단일 양수·1,000,000mL 이하. 용량과 도수 조합으로 SKU를 생성하지 않음 |
| source/revision | QID·positive lastrevid·원문 hash | 수정 시 새 snapshot과 검수 필요 |
| 가격·가용성·맛/향·인기·그룹 | 이 수집 단계에서 unknown | 이름이나 브랜드로 추론하지 않음 |

API는 info/labels/claims를 요청한다. 원문에 이미지 파일명이나 외부 URL claim이 있어도 이미지나
외부 문서를 요청하지 않으며 정제 projection은 기존 [단위/정체성 감사](CATALOG-AUDIT.md) 필드만
사용한다. `identity_review=not_performed`, `training_ready=false`를 유지한다.

## 실제 이번 관측: 원천 보류와 카탈로그 부재를 구분

주류 후보를 찾는 세 소량 검색 요청의 본문이 `maxlag` 오류였다. 초기 조사용 표시가
`payload.get("search", [])`를 사용해 빈 결과처럼 보이는 위험을 확인하고, 원문을 다시 읽어
원천 보류로 정정했다. 이때의 빈 표시를 실제 검색 결과나 제품 부재 근거로 사용하지 않는다.

간격을 둔 단일 `wbgetentities` GET(Q1154088)도 2026-10-31 21:40:28 UTC에 **HTTP200 + API maxlag**를
반환했다. 도구는 501B 응답을 `api_maxlag`로 거절하고 종료2·`accepted=false` 영수증만 남겼다.
응답 SHA-256은 `2d4668712ad01f92e63cb9bcc6e29904ab8c5fb106bdf42e5733600488f14e65`다.
이번 새 accepted item은0이며 서비스 SKU·상품군 검수나 외부 카탈로그 확보 완료가 아니다.

QID 후보는 기존 Wikipedia의 Wikidata sitelink로 발견했다. 그 페이지의 문장·맛·이미지·수치는
카탈로그에 복사하거나 학습하지 않았다. 데이터의 필드 검수는 정상적으로 확보한 item 원문에서
계속해야 한다. maxlag 임계값을 낮추거나 다른 endpoint로 같은 보류를 우회하지 않았고 이번 실행의
추가 live 요청은 중단했다. 외부 사용자가 없어서 막힌 것이 아니라 원천의 현재 응답이 보류 상태다.

기존 CC0 4항목은 같은 원문 hash `12aa1189d3b22baf51065498352b24c3d69750629e0edce75678f07b62db96a5`로
offline 재생에 성공했다. 이는 이전 브랜드3/미확정1·검수SKU0 자료의 재현이며 신규 수집이나 실제
서비스 카탈로그 증가가 아니다. 실제 검색 오류 payload의 offline 재생도 `api_maxlag`로 거절했다.
이 관측과 코드/계약 검증을 추천 품질·성능 개선·사람의 선호 성과로 환산하지 않는다.

## 실행과 완료 상태

~~~bash
# 원천이 정상인 별도 실행에서, 검수한 QID만 소량 요청한다.
uv run --locked python -m pubburi_recommendation.wikidata_collect \
  --manifest sources/wikidata-structured.json --ids Q1154088 \
  --output-dir .pubburi/entity-catalog/new-live-run

# HTTP 요청 없이 이미 확보한 payload를 재생한다. 영수증은 offline_replay로 기록된다.
uv run --locked python -m pubburi_recommendation.wikidata_collect \
  --manifest sources/wikidata-structured.json --ids Q1 \
  --snapshot .pubburi/authored-fixture.json \
  --output-dir .pubburi/entity-catalog/new-offline-run
~~~

실제 사용은 고정 HTTPS endpoint·단일 GET·최대10QID(각32자)·maxlag5·식별 UA·I/O timeout15초·10MiB 응답
상한을 적용한다. redirect·다른 action/host·임계값 변경·중복 ID는 거절한다. 자동 retry·병렬 수집·
페이지 순회·키/로그인/이미지/외부 URL 조회는 없다. 실패 후 다음 요청 시점은 원천 지침을 따른다.

- HTTP/JSON만으로 성공 처리하지 않는다. API error/warning·불명확 success·누락/추가/redirect item·
  revision/형식 오류를 원문 저장 전에 검증한다. JSON 중복 키·비유한 수치·응답 상한과 parser 재귀
  한계도 고정 진단으로 거절한다. 바이트가 작아도 깊은 입력에서 traceback을 노출하지 않는다.
- 새 디렉터리를 먼저 예약하고 초기 `accepted=false` receipt를 기록한다. 통과한 원문은 `entities.json`,
  projection은 `normalized-records.json`이다. 전체 기록을 마친 뒤 receipt를 원자적으로 갱신한다.
  파일 쓰기 실패도 accepted=false이며 소비자는 해당 상태를 먼저 확인해야 한다.
- 실패 receipt에는 고정 error code/종류·응답 hash/크기 등 안전한 메타데이터만 둔다. 원천의 error info·
  로컬 경로를 오류 로그에 복사하지 않는다. 기존 폴더/영수증/카탈로그를 덮어쓰지 않는다.
- 읽기 중 잘린 chunked HTTP 응답의 `IncompleteRead`를 포함한
  [HTTPException 계열](https://docs.python.org/3.12/library/http.client.html#http.client.HTTPException)은
  `remote_protocol_failed`로 변환한다. HTTP200·JSON처럼 보이는 일부 본문만으로 성공을 만들지
  않으며 traceback/partial body를 진단에 노출하지 않고 실패 receipt와 종료2를 유지한다.
- Content-Length가 있는 응답은 상한 내에서 읽은 바이트 수가 선언 길이와 일치해야 한다.
  `HTTPResponse.read(amt)`는 선언 길이보다 짧아도 예외 없이 반환할 수 있어 JSON 검증과 별도로
  확인한다. 선언 길이는 단일 부호 없는 ASCII 십진 표기(0 포함·최대20자리)만 허용하고
  10MiB 초과는 본문을 읽기 전에 거절한다. 중복 길이·길이와 Transfer-Encoding의 동시 선언·
  지원하지 않는 전송 인코딩·실제 chunk decoder가 선택되지 않은 선언은 보수적으로 보류한다.
  정상 길이·길이 없는 EOF 응답·정상 chunked는 허용하며 읽기 상한을 늘리거나 무제한 읽지 않는다.
- 성공 종료0은 수집/재생의 형식 검증이다. item 정체성·개별 필드 사실·판매 SKU 연결·새 카탈로그
  학습/독립 관련성·최종 평가와 Backend/Frontend 연동은 별도 미완료다. 실패 종료는2다.

CI의 [테스트·runtime-only wheel](TESTING.md)은 작은 자체 payload의 성공 재생과 maxlag 거절을
실제로 실행한다. 네트워크·실제 원본 데이터는 CI가 사용하지 않는다. 원문·개별 카탈로그·영수증은
Git에 올리지 않고 공식 근거·도구·자체 fixture·조건/집계만 공유한다.
