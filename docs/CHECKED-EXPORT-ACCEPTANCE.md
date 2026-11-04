# 검수 export를 확인하고 기존 B1 HTTP로 소비하기

`checked_export.load_checked_export`는 [business_export](BUSINESS-EXPORT.md)가 이미 만든
완료 산출물을 원권위·명시 매핑으로 다시 확인해 로드한다. `reviewed_provider_acceptance` CLI는
그 **같은 checked catalog**를 기존 content/exploration/similar/context/feedback HTTP에 보내
동결한 사실·조건·이유를 독립 검사한다. 새 endpoint·점수 모델·자동 수집·지속 모델 복원은 없다.
HTTP의 요청별 fit과 startup/health 무모델 설계는 그대로다.

## 로드 계약과 두 시계

호출자는 export 디렉터리와 manifest/raw/source-receipt/curation/business-snapshot/mapping을
명시한다. 상품군 browse DEMO에는 원래 family-review도 필수다. 원문 파일·권한/소유 근거는
계속 호출자 책임이며 파일 hash가 발행자 인증·권리 승인·서버 revision을 대신하지 않는다.

1. 디렉터리에는 `receipt.json`, `export-report.json`, `b0-demo-request.json`,
   `b1-demo-request.json` 네 파일만 있어야 한다. 부분 출력·추가 임시파일·symlink·10MiB 초과/
   중복 key/비유한 JSON은 거절한다. receipt의 completed는 실제 true여야 한다.
2. 원래 authority loader와 build_exports로 원천/검수·snapshot/mapping hash·그룹/수량·unknown·
   origin/scope를 재검증한다. 기록된 export 시각은 미래가 아니어야 하며 그때에도 snapshot이
   유효하고 fresh였어야 한다. 재생 flag가 거짓 권위나 당시부터 stale인 export를 승인하지 않는다.
3. 그대로인 기존 writer 형식(UTF-8·indent2·마지막 개행)으로 네 산출물을 다시 계산해 **전체
   바이트**를 대조한다. 요청 내용뿐 아니라 공백만 바뀌어도 거절하며 몰래 정리/덮어쓰지 않는다.
   소비한 파일들의 SHA256과 원천/snapshot/mapping hash를 metadata에 남긴다.
4. 기본 모드는 추가로 **현재 시각**의5분 freshness를 확인해 `fresh_demo_snapshot`으로
   표시한다. `--replay`는 과거 유효 시점의 아티팩트만 `historical_demo_replay`로 구분한다.
   재생은 현재 업무 export·실판매/재고·신규 카탈로그 확보가 아니다.
5. 두 모드 모두 service_catalog_approved=false·model_loaded=false와
   current_business_revalidation_required=true다. container와 별도 family browse의 권위/
   포장 gate를 그대로 보존하며 DEMO를 일반 서비스 SKU로 승격하지 않는다.

함수는 request DTO·명시 mapping·검증 metadata를 반환하고 파일을 수정하지 않는다. 모델은
읽지 않는다. 이 입력 소비 경계는 Backend의 본인 취향/권한·현재 업무 상태 재확인·B1 호출이나
React 연결의 완료를 대신하지 않는다.

## 독립 명세

명세는 schema_version1, experiment_id, evidence_kind, source_catalog_sha256,
frozen_at_utc, expected_model_fingerprint, expected_facts, cases를 가진다. `expected_facts`는
[기존 검수 fit](REVIEWED-CATALOG-FIT.md)의 nullable 상품 사실 DTO이며 정확한 매핑 key 전체를
덮어야 한다. fingerprint는 앞서 기록한 같은 카탈로그/모델 버전의 fit 지문이다. 모델/점수로
후보 정답을 생성하거나 서비스 응답에 맞춰 순위·사실을 조정하지 않는다.

| case 필드 | 의미 |
|---|---|
| provider | content / exploration / similar / context / feedback |
| profile / constraints / limit | 기존 soft/hard/상한. 현재 명세는 제공자의 기존 기본 탐색 정책·floor를 사용 |
| exclude_keys | 명시 매핑 key의 hard 제외. unbound 사업 ID를 넣지 않음 |
| reference_keys | similar는1개, context는1–20개. 다른 경로에는 없음 |
| positive_keys / negative_keys | feedback에만 각각 최대20개. 기존 negative 우선/모든 알려진 그룹 제외 |
| expected_eligible_keys | 독립 사실/그룹/조건으로 선언한 적격 key. reference가 사용 불가해 미계산이면 null |
| expected_item_keys | 실제 반환을 기대하는 key와 순서. 양수/그룹 선택·빈 fallback과 limit을 구분 |
| expected_comparisons | 각 반환 key의 profile 비교는 null, 실제 winning reference는 해당 명시 key |
| expected_fallback / expected_representation_fitted | 원래 경로별 사유·usable fit 여부. 빈 후보가 nonempty catalog fit을 지우지는 않음 |
| fact_basis | 원천 사실과 명시 DEMO 조건·고정 기대의 근거 |

이 CLI는 매핑 안의 알려진 기준만 사용한다. 없는 사업 ID를 만들어 넣지 않으며 missing-reference
경계 전체를 검증했다는 뜻은 아니다. 그 계약은 기존 제공자의 별도 authored 회귀를 유지한다.

HTTP 전에 사실·key·시각·독립 eligibility와 요청512KiB를 확인한다. 응답에서는 typed schema와
명시 후보/순서·eligible/fallback·fit 지문, 실제 기준/profile 출처, 원기여의 허용 사실/양수·합,
활성 hard 이유·actual/target/unit·top3 생략/4KiB를 검사한다. 생산 scorer/formatter로 기대값을
만들지 않는다. 원래 context 최대 매치나 탐색 MMR을 사용자 선호/다양성 품질로 해석하지 않는다.
feedback은 반환 item이 없어도 기준 목록·실제 그룹/available·negative 우선 blocked 상태를
응답 단위에서 대조한다. 미평가 기준의 null과 available 기준의 지원 토큰·활성 수치/평가 수,
informative 수·ranking_mode·중복 없는 그룹 제외 수를 동결 요청/카탈로그 사실로 확인한다.

응답 단위 목록 검사는 item loop 밖에서 실행한다. 빈 결과도 목록/상태/개수 검사를 생략하지 않는다.

| 제공자 | 독립 ID·그룹·순서/개수 대조 |
|---|---|
| content | 동결 item ID/순서·eligible/fallback·fit. 별도 선택/기준 목록 없음 |
| exploration | selections의 ID/순서가 items와 같고 각 그룹이 checked catalog와 일치. 선택 수·고유 그룹 수·limit·pool 개수 경계와 선택/빈 fallback 상태 대조 |
| similar | 실제 기준 ID/그룹/available 상태와 그 그룹의 전체 제외 수. 사용 불가이면 제외 수 null |
| context | 정렬된 기준 ID/그룹/상태·평가 수/진단, 알려진 모든 기준 그룹의 중복 없는 제외 수. 사용 가능 기준이 없으면 제외 수 null·미평가 진단 null. matches가 반환 순서와 선언한 winning ID에 정확히 일치 |
| feedback | 기존 positive/negative 기준·상태/평가/제외 수 대조와 함께 matches의 ID/순서가 items에 정확히 일치. 빈 결과의 phantom match도 거절 |

탐색 MMR 점수/유사도나 최대 매치 점수를 다시 계산하지 않는다. pool 검사는 반환 개수의
논리적 경계이며 독립적인 랭킹 품질 정답을 새로 만드는 검사가 아니다.
공통 profile 진단은 입력의 명시 atomic 종류/값이 checked catalog 사실에 존재하는지와 활성
수치 범위로 지원/unknown 개수·활성 필드를 대조한다. similar의 사용 불가 기준은 평가 없이
0/0/[]를 유지한다. 반환 item의 유무가 이 진단 검사를 생략하는 조건이 되지 않는다.

## 실행·완료와 실패

~~~bash
uv run --locked python -m pubburi_recommendation.reviewed_provider_acceptance \
  --export-dir .pubburi/reviewed-export \
  --manifest sources/wikidata-structured.json \
  --input .pubburi/source/entities.json --source-receipt .pubburi/source/receipt.json \
  --curation .pubburi/curation.json --business-snapshot .pubburi/business.json \
  --mapping .pubburi/mapping.json --spec .pubburi/frozen-provider-cases.json \
  --base-url http://127.0.0.1:12345 --output-dir .pubburi/provider-acceptance-new
~~~

예시 포트는 실제 실행 시 본인이 예약한 loopback 포트로 바꾼다. family authority에는
`--family-review`를 더하고, 과거 export를 재생할 때만 `--replay`를 명시한다. 원문/요청/
모델·보고서는 Git에 추가하지 않는다.

대상은 명시한 http://127.0.0.1:port origin만 허용한다. 외부 호스트·인증정보·query/path·
redirect·환경 proxy·재시도는 없다. caller가 실제 소유를 확인하며 loopback 자체가 인증은 아니다.
응답은10MiB, 각 HTTP 클라이언트 예산은30초다. 서버의 기존512KiB/10초 수신 경계와
CPU fit 시간 보장은 구분한다.

새 private output만 쓰며 기존 output은 입력 읽기 전에 보존한다. HTTP 뒤에도 입력을 다시
검증해 파일 변경·fresh 모드의 만료를 거절한다. 동결 spec도 다시 읽어 최초 raw hash와 비교하며
변경·삭제되면 이전 spec hash로 완료/통과 보고서를 발행하지 않는다. 이는 원자적 파일/업무
snapshot 보장이 아니다.
완성 receipt는 completed=true와 passed를 별도로 기록한다. exit0은 해당 계약 통과,
exit1은 완료된 결과의 계약 위반, exit2는 입력/전송/실행 오류다. 중간 실패는 완료로 표시하지 않는다.

보고서에는 전체 요청/응답과 실패 case가 있어 ignored private에만 보관한다. CI는 authored
자료로 같은 실제 CLI/HTTP를 실행하며 기존 JUnit/배포 요약만 업로드한다. 실제 source·모델/
업무 snapshot을 CI artifact에 넣지 않는다. 사용자 품질/성능·whole R/AI03·MVP 완료 지표가 아니다.

[실행/표본·정정 기록](plans/2026-11-04-checked-export-provider-acceptance.md) · [검증](TESTING.md)
