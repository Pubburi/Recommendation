# GTIN 외부 식별자 metadata의 승인 경계

기준 main `aef0283`의 포장 감사는 GTIN 문자열·체크숫자와 rank/snak/value type을 검증하지만
명시 `mainsnak.property/datatype`은 확인하지 않았다. P3962 bucket의 숫자 문자열이 정상이면
다른 property·item datatype으로 선언된 claim도 usable GTIN으로 처리돼 source curation에
사용됐다. checksum과 statement의 의미가 다른 경계인데 전자만으로 후자까지 승인한 결함이다.

## 구현 전 고정과 재현

2026-11-03 03:28:54.956561 UTC에 자체 작성한 두 손상 조건(property=P31,
datatype=wikibase-item)과 별도 정상/metadata 생략/공유 식별자 대조를 동결했다. 명세 SHA256은
`5d811e4a857c71dfa15b4aafeb7d40c638d764a9071b922e5b52169c98e52133`이다.
GTIN·라벨/수량·P31과 수동 checked facts/scope는 그대로 두고 GTIN metadata만 바꿨다.

실제 offline collector→package audit→source_catalog CLI를 실행했다. 같은 accepted receipt/
raw/revision·manifest/curation hash에서 변경 전 손상2/2가 usable GTIN·카탈로그로 승인됐다.
정상/생략2개는 각각 승인되고, 별도2item의 같은 비교 키는1공유 그룹/양쪽 보류였다. 원문과
기대는 모델/코드 결과로 만들지 않았으며 [원값/분모](../measurements/2026-11-03-gtin-statement-metadata.md)를 보존한다.

## 수정과 선택

[공식 P3962](https://www.wikidata.org/wiki/Property:P3962)는 외부 식별자다. property가 명시되면
P3962, datatype이 명시되면 external-id여야 한다. legacy의 생략된 중복 metadata는 유지한다.
명시 모순은 `gtin_statement_requires_review`와 usable=false로 남겨 기존 포장 보류·curation
gate가 거절하게 한다. 원래 문자열·체크숫자·14자리 비교 키를 삭제/수정하지 않는다.

메타데이터가 잘못됐다고 활성 claim을 collision 검사에서 버리면 정상 item의 같은 식별자를
숨길 수 있다. 기존 structurally-usable 비교 근거와 양쪽 공유 보류는 유지하며, 이 값의 GTIN
할당/진실성을 새로 승인하지 않는다. deprecated는 계속 활성 충돌에서 제외한다. 기존 공통
관계/수량 helper나 서비스 모델을 리팩터링하지 않고 이 external-identifier 경계만 수정한다.

## 같은 조건의 결과

같은 동결 입력/accepted receipt의 거짓 curation 승인은2/2→0/2였다. 고정 metadata issue·
usable=false와 `curation_cannot_override_unresolved_source_hold`/exit2·출력 미발행을 확인했다.
정상/생략2개와 공유 식별자1그룹/양쪽 보류, 원래 GTIN 문자열·체크숫자·키는 전후 같았다.
실제 기존 원천 카탈로그1·curation,11상품군 B1/M1의 전체 보고서/지문도 이전 저장본과 byte
동일했다. 신규 원천·업무 매핑/서비스 fit은0이며 관련성·시간 성능·자연 오류율 성과가 아니다.

Python3.12.14·고정 uv0.13.6의 `./scripts/check.sh`가 `UV_OFFLINE=true`에서 전체 성공했다.
저장소/locked sync·Ruff/format·pytest843개(새22개), B0/content 시나리오 각8/8·새 sdist/wheel과
runtime-only 격리 설치를 통과했다. checkout 밖 `python -I`의 실제 offline collector→package
audit→curation에서 별도 property/datatype2조건과 collision 대조의 고정 보류·checksum/key
보존·exit2/미발행을 확인했다. 기존 관계/수량·cohort/M1/업무 export/fit CLI와 실제 health/
B0/B1/exploration/similar/context/OpenAPI·production10초 부분 본문408도 통과했다.
기존 TestClient deprecation 경고1개를 남긴다. 검사 수/CI 시간은 앱 성능 수치가 아니다.

원본/영수증·모델/로그는 ignored에만 두며 최신 head 필수 CI·완료 Codex/native 미해결0·
Squash/main CI·브랜치 정리는 별도 최종 게이트다. 현재 로컬 검증과 병합 완료를 구분한다.

## README와 후속

이 수정은 기존 source metadata→학습/정체성 의미 보존과 인접한 식별자 감사다. 새 독립
서비스/카탈로그 품질 영향의 더 강한 근거가 아니므로 README 전체와3사례/순서·부족1을
보존한다. checksum/metadata를 나눠 네 번째 사례로 세지 않는다. source11상품군·업무 DEMO1·
문맥11과 자체 손상/대조의 분모도 합산하지 않는다. 실제 다중 서비스 SKU/명시 업무 매핑·
독립 사실 평가와 전체 DAT02–04/AI03은 계속 필요하며 사용자/미래 로그를 선행 대기로 삼지 않는다.
