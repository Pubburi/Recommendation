# 두 제조사 source cohort의 표현 지원 범위

- 기준 main `7418d436`, Python3.12.14·locked scikit-learn1.9.1. 새 source GET/DB/업무 API는
  호출하지 않았다. 기존 snapshot2개는 각각6/8원천 항목이며 그중 검수 상품군5/6개를 선택했다.
- 선택11source ID/11curator group·고정 revision11, ID 중복0·trim/casefold label 충돌0이다. 변형/
  그룹은 이전 명시 상품군 검수 범위다. barcode/물리 SKU·기업집단 관계까지 검증한 것이 아니다.
- 학습 전에2026-11-01 17:45:04 UTC에 전체 명세/hash·사실·5fit/6transform·독립 exact-P31
  질의/정답/cutoff를 동결했다. 원문·두 receipt/review·명세·모델 파라미터/원순위는 ignored다.
  각 authority의 accepted/ID/revision/manifest/hash와 strict P31/P176 관계를 확인했다.
- 소스 제조사 관계는 이름에서 추정하지 않고 unqualified P176 값을 사용했다. 같은 source ID가
  두 authority의 선택에 나타나면 자동 합치지 않는다. 두 source 제조사 집합/상품군 분할은 겹치지 않는다.

| 실제 관측 | 결과·분모 |
|---|---|
| source 상품군 | 총11/제조사 관계2. 학습5/제조사1, 변환6/미관측 제조사1 |
| 텍스트 fit | 5×7/rank5, 학습 class6토큰·제조사1토큰 |
| 학습 도수 | 5/5관측, min5.3–max10vol%, 거리 활성 |
| 학습 용량 | 0/5관측, all_unknown·비활성 |
| 변환 수량 | 도수/용량 각각0/6관측. 허용 단위/문맥 부족을0으로 채우지 않음 |
| 변환 제조사 | 토큰OOV6/6. 실제 producer 관계를 학습 입력에 넣지 않음 |
| 변환 text 지원 | nonzero1/6·zero5/6. 공유 class1개만 지원 |
| 사실 평가 질의 | 총6/질의별 후보5, 양성1질의·나머지5질의 양성0으로 지표 생략 |

양성 질의1개의 관련 후보는 source-ID 문자열 참고순2위·TF-IDF cosine1위였다.

| 카탈로그 사실 관련성(양성 질의1개) | source-ID 참고순 | 표현 cosine순 |
|---|---:|---:|
| Recall@1 | 0 | 1 |
| NDCG@3 | 약0.63093 | 1 |

Macro 평균의 실제 분모는
1이며 text 지원1/6·무양성/zero-vector5질의를 숨기지 않는다. 참고순은 기존 source 실험의
고정 정렬이고 Backend 서비스 B0나 운영 기준 모델이 아니다. 이를 전체 추천 개선율로 계산하지 않는다.

이전 한 제조사 내4fit/2transform은 공통 producer 토큰이 미지원 스타일에도 남았다. 새 설정은
다른 source 제조사를 변환에 두어 그 신호가 사라지는 조건을 드러냈다. 데이터/분할이 다른
실험이므로 전후 품질 개선 비교로 합산하지 않는다. 목적 표본·두 제조사·한 양성 사실 정답이며,
입력 P31과 정답 관계를 공유한다. 사용자 선호/의미 관련성·신규 포장 SKU/기업 관계 일반화,
최종 평가·실서비스 카탈로그/Backend 연동은 여전히 별도다.

최종 동일 입력 두 실행의 전체 보고서·fit fingerprint와 원래 frozen spec hash 일치를 확인했다.
새 네트워크 수집·모델 복잡도 증가·SVD 채택·지연/메모리 성능 개선 주장은 없다.
