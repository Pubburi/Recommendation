# 분류·생산자 관계의 원천→학습 정합성

기준 main `7ba8c9d`의 `catalog_audit.item_ids`는 `datavalue.value.id`가 QID 모양이면 관계로
받았다. P31/P176 bucket과 명시 property/datatype·snak/value/entity 타입·numeric-id가
모순이어도 단독 `source_family_experiment`는 정규화된 사실과 명세가 같다고 판단해 실제
TF-IDF 문서/어휘·DF-IDF를 fit했다. 별도 cohort의 더 강한 검증은 공통 정규화·단독 실험·
포장 curation 경로를 보호하지 못했다.

## 구현 전 고정과 실제 기준선

2026-11-02 22:44:44.088110 UTC(한국 시간11월3일)에12개 자체 손상 조건과 별도 포장2개를
코드 수정 전에 동결했다. 명세 SHA256:
`9d7b3ef4837ba9a930872b22fd53158b1b9c902e730aa2588a854d6caa9d1579`.
자료는 실제 원천 오류가 아닌 직접 작성한3상품군/2fit·1transform이다. P31/P176 각각의
property/datatype/value-type/entity-type/numeric-id/snaktype 모순6종만 학습 Q1에 넣었다.
수량과 다른 상품군의 정상 사실은 그대로다.

실제 offline collector가 만든 accepted receipt와 같은 raw/review/hash를 단독 audit→family
CLI에 전달했다. 변경 전12/12가 거짓 관계 사실을 승인해 모델 보고서를 발행했다. 별도 포장
조건은 잘못된 property의 can, 유효 can 옆의 잘못된 brand datatype이다. 같은 collector→
curation CLI는 mixed-type 메모가 있는 두 경우 모두2/2 카탈로그를 발행했다. [분모/원값/
보존 근거](../measurements/2026-11-03-source-relation-integrity.md)를 따른다.

## 수정과 대안

- 공통 `item_relations`는 생략한 중복 legacy metadata는 유지하고, 명시된 rank/snak/
  property/datatype/value type·item/numeric identity가 일치하는지 확인한다. 관계 ID는
  기존 모델 계약의 최대32자 QID다. qualified/불명확한 활성 관계를 무조건 사실로 평탄화하지 않는다.
- 같은 property에 문제가 하나라도 있으면 전체 집합을 `[]`와 고정 relation issue로 보존한다.
  이는 검수한 '관계 없음'이 아니라 미확인 집합이다. 정상 이웃만 남기면 부분 집합을 완전한
  사실로 오인할 수 있어 채택하지 않았다. deprecated는 제외하고 다른 property/수량은 보존한다.
- 기존 단독 fit 전 사실 대조를 재사용한다. 거짓 nonempty 선언은 fit 전에 거절하고, honest
  empty 선언이면 나머지 확인된 사실만 fit한다. cohort의 더 강한 필수 metadata 검증은 유지한다.
- 포장 감사에는 `instance_of_relations_require_review` 보류를 추가한다. 잘못된 brand를
  제거한 뒤 유효 can만 보고 mixed grain이 해결됐다고 판단하지 않으며, 이 보류는 수동
  mixed-type 해석으로 덮을 수 없다. 정상 수량/GTIN과 기존 명시 scope는 변경하지 않는다.
- audit의 `relation_issues`와 `quantity_issues`를 구분한다. 고정 진단에 원래 ID/입력값을
  반사하지 않고 전체 레코드·기존 snapshot을 삭제하거나 메타데이터를 보충 저장하지 않는다.

## 같은 조건의 결과와 검증

같은 동결 입력/accepted receipt/review/hash에서 거짓 관계 사실·단독 fit 승인은12/12→0/12,
별도 포장 curation 승인은2/2→0/2였다. 모두 고정 진단·입력 실패/보고서 미발행을 확인했다.
honest empty12/12는 나머지 정상 사실·수치2관측으로 fit했다. P31의 잘못된 고유 토큰은
없어졌고, P176의 공유 producer 토큰은 유효 Q2가 있으므로 유지하되 DF2→1/IDF1→1.405465가
됐다. 이를 전체 토큰 제거·추천 품질/성능이나 자연 발생 오류율의 개선으로 표현하지 않는다.

기존 실제11상품군의 B1 전체 보고서/지문과 고정 M1 전체 보고서/지문은 수정 전후·이전
저장본에서 byte 동일했다. 기존 실제 원천 포장 후보1개의 전체 source-catalog/curation 보고서도
이전과 byte 동일했다. 새 source GET·업무 매핑·서비스 카탈로그 fit은0이며 원본은 보존했다.

Python3.12.14·고정 uv0.13.6의 `./scripts/check.sh`가 외부 다운로드를 비활성화한 상태에서
전체 성공했다. 저장소/locked sync·Ruff/format·pytest821개(새55개), B0/content 시나리오
각8/8·새 sdist/wheel·runtime-only 격리 설치를 통과했다. checkout 밖 `python -I`의 실제
offline collector→family CLI에서 별도 손상4조건의 거짓 사실 거절/honest empty fit·DF-IDF와
포장2조건의 curation 거절/미발행을 확인했다. 기존 cohort/M1·원천/업무 export/fit CLI와
실제 health/B0/B1/exploration/similar/context/OpenAPI·production10초 부분 본문408도 통과했다.
기존 TestClient deprecation 경고1개를 남긴다. 초기 새 테스트의 큰 Python 정수 자동 ID 생성은
pytest의 문자열 변환 제한으로 수집 실패해 명시 테스트 ID로 고쳤고, 제품의 JSON 제한은 그대로다.

최신 head 필수 CI·완료 Codex/미해결0·Squash/main CI·ff-only/병합 브랜치 정리는 조정자의
최종 게이트이며 현재 로컬 검증 완료와 구분한다. 원문/영수증·모델/로그는 ignored에만 보관한다.

## README와 후속

이번에는 categorical identity→문서/DF-IDF와 포장 grain의 잘못된 승인을 실제로 수정했다.
다만 기존 CS07의 원천 명시 metadata→학습 입력 의미 보존과 인접하며, 독립된 서비스/카탈로그
품질 영향의 더 강한 근거는 아직 없다. 현재 CS05/06/07 세 본문·순서와3/4·부족1을 보존하고
기능 행만 갱신한다. 같은 원천 검증 문제를 수량/범주형으로 나눠 네 번째를 채우지 않는다.

실제 다중 서비스 포장 카탈로그·명시 업무 매핑/고정 독립 사실 평가·전체 AI03/DAT02–04는
계속 필요하다. 상품군 QID·문맥별 용량·단일 업무 DEMO와 이번 허구 손상을 합산하지 않고,
aT 보류 재시도/우회·새 계정/외부 연락·이미지/본문 수집이나 사용자/미래 로그 대기를 추가하지 않는다.
