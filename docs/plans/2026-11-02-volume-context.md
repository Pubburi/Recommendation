# 포장 문맥별 용량 관측 보존

## 범위와 사전 사실

- 대상 DAT02/AI03의 데이터 준비 일부. 기존6상품군의 P2234/P518를 statement grain으로 보존하는
  실행 가능한 오프라인 제품 도구다. 기존 API·family scalar 정규화·모델·source export gate는 유지한다.
- 실제 원천의 qualified/multiple volume을 가족 단일 수치로 취급하면330mL와20L가 충돌한다.
  기존 scalar unknown은 올바른 처리다. 별도 관측이 없었던 정보 보존 공백을 해결한다.
- 공식 [P518 정의](https://www.wikidata.org/wiki/Property:P518)와
  [CC0 구조화 범위](https://www.wikidata.org/wiki/Wikidata:Licensing)를 검수했다. 문맥 정의 개체4개는
  캔·케그·병 범위의 수량 문맥으로만 검수하며 완성 포장/판매 SKU 인증으로 쓰지 않는다.
- 2026-11-01 UTC 고정 소량 GET1회/4ID/maxlag5/기존 바이트·시간 상한/자동 재시도 없음으로
  문맥 정의 snapshot을 accepted 수집했다. 주류 상품 신규 수집이 아니며 원문/receipt는 ignored에만 둔다.
  제조사 페이지의 이전429/aT 자동 승인 거절·외부 문의/가입·비용·이미지 수집을 재시도하지 않았다.
- 코드 전19:51:36.072628Z 고정 spec SHA-256:
  `3d4f1168fb86664cd8c6c2b917189af4cb09b201a2187a6ec4de4d07875171bb`.
  명시 기대는6가족/11claim,330mL5·20,000mL5·750mL1이다. 단위 산술과 원문 P518를 사람이 대조했으며
  코드 출력으로 기대값을 만들지 않았다. 가족 volume unknown6/6·신규 업무 매핑/fit0을 먼저 고정했다.

## 선택과 구현

- 기존 scalar에 첫 값·평균·최댓값을 넣는 대안은 가족 전체의 용량을 오인한다. qualifier를 무시한
  새 SKU 생성도 포장 식별/GTIN/pack count 없는 자료를 과대 승격한다. 두 대안 모두 채택하지 않았다.
- `volume_context`가 두 accepted receipt와 raw/manifest/review/spec SHA·정확 ID/revision을 각각 검증한다.
  정의의 라벨/revision/수동 scope와 명시 product_family·가족 scalar unknown을 확인한다.
- 같은 statement의 quantity와 단일 reviewed P518만 연결한다. 정수/부동소수로 강제 변환하지 않고
  정확한 십진 문자열 mL를 출력한다. 불명확한 rank/type·단위 namespace·정밀도/범위·qualifier·중복
  family/context는 unknown/hold다. statement 누락/중복·다른 원천 ID는 고정 실패로 처리한다.
- 별도 source observation에 같은 family_group·원문 statement ID/revision·정의 revision·reference 개수를
  남긴다. ABV/GTIN/BackendID는 null이며 모델 fit을 실행하지 않는다. 안전한 새 ignored 보고서만 발행한다.
- CLI/정제는 네트워크·DB·모델을 요구하지 않는다. 단일 원천당 최대10 ID/상품군당100 volume claim과
  공통 파일10MiB 상한을 유지한다. 기존512KiB/10초 추천 HTTP 수신·health/API 동작은 변경하지 않는다.

## 실제 실행과 검증

첫 실제 실행은6가족·4정의·11활성 claim을 각각 보존했고 보류0이었다. 수량 분포는 사전 기대와
같다. 가족 scalar unknown6/6을 그대로 유지했고 신규 Backend 매핑0·모델 fit0이다. 이 결과는
정보 보존/정합성 증거이며 시간 성능·추천 관련성·사용자 만족도 개선이 아니다.

동일 동결 입력의 두 실행은 **보고서 전체가 동일**했고 파일 SHA-256은 모두
`29e87def41172d9d915b79733965815a1f237138aace3a408aa8a6941b046d35`다. 문맥 정의 수집은
19:51:06.344045Z/HTTP200/12,688B/accepted4였으며 제조사 조회·외부 본문/이미지 수집은 없다.

Python3.12.14·잠금 의존성의 `./scripts/check.sh` 전체가 성공했다. Ruff/포맷·589개 pytest·
기존 고정 시나리오와 새 sdist/wheel 빌드, runtime-only 격리 설치의 `python -I` 실제 관측 CLI
성공/authority 불일치 실패·기존 health/B0/B1/OpenAPI HTTP를 확인했다. 새 동작의 회귀는61개,
관련 기존 경계를 포함한 사전 검사는187개다. 기존 TestClient deprecation 경고1개를 숨기지 않았다.
검사 수/CI 시간은 서비스 성능이나 데이터 품질 지표가 아니다. 원본·검수/사실 명세·개별 관측·
영수증·원값·모델은 Git에 넣지 않는다.

## 후속과 README 판단

관측11개는 검수 완료된 포장 SKU11개가 아니다. 문맥 정의만으로 개별 상품 정체성·판매/재고·
가격/도수/GTIN·권리가 모두 확정되지 않는다. 다음은 허용 근거로 포장 정체성·필수 수치/식별자를
검수하고 실제 업무 snapshot/명시 매핑을 연결하는 일이다. API 제공자 PostgreSQL/JPA/Flyway 전환 후
계약을 재확인하되 추천에 업무DB 직접 의존성을 넣거나 사용자 로그를 기다리지 않는다.

현재 README의 실제 원천 완료 상태/HTTP200 오류 분리와 실제 JSON 입력 의미 유실 수정 사례는
더 넓은 실행 경계와 재현된 실패/대안 근거를 제공한다. 이번 분리는 유용한 데이터 준비 기여지만
실SKU/다중 업무 카탈로그·모델/품질 결과 없이 독립 대표 사례를 억지로 늘리지 않는다.
현재2/4와 순서를 보존하며 부족2개는 실제 개발·근거 확보로 채운다.
