# GTIN metadata 모순의 같은 CLI 전후 재현

실제 source 오류율·SKU 할당·추천 품질·성능이 아닌 자체 손상 입력의 정합성 실험이다.
기준 main `aef0283`, Python3.12.14·같은 잠금 의존성에서 두 primary 조건과 별도 대조를
코드 전에 동결했다. 시간은2026-11-03 03:28:54.956561 UTC, 명세 SHA256은
`5d811e4a857c71dfa15b4aafeb7d40c638d764a9071b922e5b52169c98e52133`이다.

두 primary는 P3962 bucket의 GTIN 문자열을 그대로 두고 property=P31 또는
datatype=wikibase-item로 바꾼 것이다. 명시 can/라벨·도수5/용량500과 자체 GTIN/checked
facts·scope를 고정했다. 실제 offline collector가 만든 accepted receipt/raw/revision/hash를
전후 그대로 재사용해 package audit→source_catalog CLI를 실행했다. 별도 정상 external-id,
metadata 생략과 두 item의 공유 키를 대조했다. 이들을 primary 오류 분모에 합산하지 않는다.

| 관측 | 변경 전 | 변경 후 |
|---|---|---|
| primary 모순 claim의 usable 승인 | 2/2 | 0/2 |
| primary 모순 claim의 실제 curation/report 발행 | 2/2 | 0/2 |
| 별도 정상/metadata 생략 curation | 2/2 | 2/2 |
| 별도 공유 식별자 그룹/보류 item | 1 / 2 | 1 / 2 |
| 원래 문자열·checksum·14자리 비교 키 | 보존 | 동일하게 보존 |

변경 후 issue는 `gtin_statement_requires_review`, usable은 false다. raw 형식/checksum에
대한 structurally_usable은 true로 남기며 이를 실제 할당·상품 진실성으로 해석하지 않는다.
curation은 `curation_cannot_override_unresolved_source_hold`·exit2로 새 디렉터리를 발행하지
않았다. 같은 키를 가진 metadata 손상 claim도 기존 충돌 근거에서 제거하지 않아 정상 item의
공유 보류가 숨겨지지 않았다. deprecated는 이 활성 충돌과 별개다.

전후 실행 proof SHA256은 각각
`fa18054640fc31f1892046f466edb2ad73150fd5ad2db04ebaf31618572e84e8`,
`5d8435ceed1b83c1ef879276f388699852d96e70be37419f86431f3223553205`다.
원문·영수증·개별 감사/모델 결과와 로그는 ignored에만 있다.

기존 실제 accepted GTIN4개는 모두 property=P3962/datatype=external-id/value type=string인
정상 metadata였다. 기존 source-catalog/curation의 전체 파일은 각각
`f013375a88ffd7fb990ede04de3316e24318a486ae65a641c66880ca87cce0ff` /
`5f5c7111804cf24d540941f846eee726cc9c2e8b9fd848cf1914785353abd141`로 그대로였다.
기존11상품군 B1/M1을 전후 실제 재실행한 전체 파일도 이전 저장본과 byte 동일했고 SHA256은
각각 `dcdea43cca59628cd6c3041db2f00393bf1e1ca0c3f5be781f529ae6adad73e2` /
`d60979b7c20732231aacb7054788cf140ea25b9bfb88744f9ff09d336a24760b`였다.
신규 상품 snapshot 수집·업무 mapping/서비스 fit0이며 source11/DEMO1/문맥11과 합산하지 않는다.
이것은 전체 카탈로그 품질·권리 승인이나 AI03 완료가 아니다. [작업/검증 기록](../plans/2026-11-03-gtin-statement-metadata.md)을 따른다.
