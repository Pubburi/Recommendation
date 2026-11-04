# 명시 관계 모순의 실제 CLI 전후 재현

기준 커밋 `7ba8c9d`에서 자체 작성한 관계 손상 입력을 먼저 동결하고 같은 CLI로 전후를
실행한 정합성 실험이다. 실제 Wikidata의 오류 발생률·사람의 선호/추천 품질·성능 측정이 아니다.
원문/검수/영수증·개별 모델 파라미터와 로그는 ignored에만 보존한다.

## 고정 조건

- 동결:2026-11-02 22:44:44.088110 UTC, 명세 SHA256
  `9d7b3ef4837ba9a930872b22fd53158b1b9c902e730aa2588a854d6caa9d1579`.
- Python3.12.14·같은 잠금 의존성과3개 허구 상품군, 학습2·변환1을 사용했다. 학습 Q1의
  P31 또는 P176만 손상하고 양쪽 모두 raw의 QID 모양은 유지했다. 명시 property/datatype/
  value-type/entity-type/numeric-id/snaktype6종×2property=12조건이다.
- 각 원문을 기존 collector의 실제 offline CLI로 재생해 accepted receipt·정확 revision/
  raw/manifest hash를 결속하고 명시 product_family 검수·사실 명세로 audit/fit CLI를 실행했다.
  수정 후에는 같은 파일/영수증/검수를 재사용해 stale authority 거절과 구분했다.
- 별도2조건은 자체 GTIN/수량/라벨을 가진 포장 입력의 잘못된 can property와, 유효 can 옆의
  잘못된 brand datatype이다. 명시 checked facts와 mixed-type scope를 고정해 실제
  collector→source_catalog CLI를 실행했다. 이2개를 상품군12개의 분모와 합산하지 않는다.

## 관측 결과

| 고정 분모/경로 | 수정 전 | 수정 후 |
|---|---|---|
| 손상 관계를 nonempty 사실로 정규화 | 12/12 | 0/12 |
| 같은 거짓 사실 선언으로 실제 family fit/report 승인 | 12/12 | 0/12 |
| honest empty 선언의 나머지 사실 fit | 별도 수정 후 대조 조건 | 12/12 |
| 별도 손상 P31의 source curation/report 승인 | 2/2 | 0/2 |

거짓 사실은 `manual_facts_conflict_with_reviewed_source`·exit2로 fit/report 전에 거절됐다.
honest empty는 같은 원문에서 해당 관계를 미확인으로 선언한 조건이다. P31 손상6조건에서는
기존의 잘못된 `instance_of:Q10`이 학습 vocabulary에서 빠졌고 유효 Q2 class/producer는 남았다.
P176 손상6조건은 producer:Q20이 유효 Q2에도 있으므로 토큰 자체는 남는다. 대신 잘못된 Q1을
문서 빈도에 합산하지 않아 DF2→1, IDF1→`log(3/2)+1 = 1.4054651081081644`가 됐다.
수치 fit은 모든 조건에서 기존 도수2관측/min5/max15 그대로였다.

포장2조건은 `instance_of_relations_require_review`가 생겨 기존 mixed-type 메모로도
해제되지 않았다. 실제 curation은 `curation_cannot_override_unresolved_source_hold`·exit2이며
새 catalog 디렉터리를 발행하지 않았다. 정상 can과 잘못된 brand를 분리해 전자만 자동 승인하는
우회도 막았다. 모든 unknown/보류는 원문 변경이나 실제 상품의 정체성 판정이 아니다.

변경 전 실행 proof SHA256은
`8723fab168731e8f11fbecc3a7b663a8d0956ac17b335c86d5748182f3ec77c3`, 변경 후는
`796afe1a4db29cc7a6add20e33c3b085eb6b8bcf16815b388748e2ba13bb2966`다.
실행 시각/원값을 보존했으며 사후 기대값을 모델 점수로 생성하지 않았다.

## 실제 정상 원천 대조와 한계

수정 전후 실제 기존11상품군/5fit·6transform의 B1과 고정 M1 CLI를 각각 재실행했다. 각 전체
보고서는 이전 저장본과 byte 동일했다.

| 보존 대상 | SHA256 |
|---|---|
| B1 전체 보고서 | dcdea43cca59628cd6c3041db2f00393bf1e1ca0c3f5be781f529ae6adad73e2 |
| 고정 M1 전체 보고서 | d60979b7c20732231aacb7054788cf140ea25b9bfb88744f9ff09d336a24760b |
| 기존 실제 source-catalog | f013375a88ffd7fb990ede04de3316e24318a486ae65a641c66880ca87cce0ff |
| 기존 실제 curation 보고서 | 5f5c7111804cf24d540941f846eee726cc9c2e8b9fd848cf1914785353abd141 |

B1 fingerprint는 `0b1dea7937e89b8bf3cbe5180ec2ea8a6a9fbe467725a5e9340021bde0853748`,
M1 후보는 `4a8decc5307e26068ba8305ce997f3caa1d2d03a170d65910980a8d66a7118ee`로 그대로다.
같은 원천의 검수·권리·unknown과 기존 M1 미채택도 유지한다. 수량/단위 수정의 이전 손상10조건,
실제 업무 DEMO1상품·문맥11은 다른 실험/분모다. 신규 원천 수집·업무 mapping/서비스 fit0이며
모델 품질/전체 AI03 완료를 주장하지 않는다. [계획/검증](https://github.com/Pubburi/Recommendation/blob/39647aab11e2bb212a23162ad1c57596860b32a7/docs/plans/2026-11-03-source-relation-integrity.md)을 따른다.
