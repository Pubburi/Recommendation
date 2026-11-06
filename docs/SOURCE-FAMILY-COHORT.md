# 검수 snapshot을 유지한 미관측 제조사 실험

`source_family_cohort`는 이미 확보한 CC0 원문/영수증/검수2–4세트를 각각 검증한 뒤, 명시된
상품군을 하나의 고정 실험으로 연결한다. 이전 단일 snapshot의 TF-IDF·수치 fit과 독립 사실
평가기를 재사용하며 서비스 랭커/HTTP·Backend 상품 ID·업무 DB 연결을 추가하지 않는다.

## 연결과 분리 계약

- manifest의 구조화 normalization/fit 허용과 파일 hash를 먼저 확인한다. 각 snapshot은
  고정 raw·accepted receipt·review hash를 별도로 갖고 기존10ID·정확 revision/요청 ID·원천 오류
  가드를 통과해야 한다. 합친 자료를 새 수집 receipt로 만들거나 신규 원천 획득으로 세지 않는다.
- snapshot 이름/원문 hash는 달라야 하고 선택 source ID는 세트 사이에서도 겹치면 거절한다.
  같은 ID의 자동 overwrite·revision 선택/합치기를 하지 않는다. 전체 선택 집합은 동결 사실/
  family group을 정확히 덮어야 한다. 그룹은 curator가 선언한 상품군이며 물리 포장 SKU의
  중복 부재나 실제 제조사/판매의 인증이 아니다.
- 선택 항목은 이름이 있는 검수 product_family다. P31/P176은 원문의 normal/preferred·
  unqualified·entity-valued 관계와 명시 사실을 대조한다. 이름으로 제조사를 추정하거나
  source ID를 업무 ID로 바꾸지 않는다. 관계가 미확인/문맥 의존/모순이면 별도 검수가 필요하다.
  최소형/기존 authored 입력은 중복적인 snak `property`/`datatype` 생략을 유지하지만, 원문에
  명시됐다면 현재 P31/P176 bucket 및 `wikibase-item`과 일치해야 한다. 모순을 버리거나
  원문에 없는 메타데이터를 보충 저장하지 않는다. 수집 accepted/hash 일치가 관계 사실을 승인하지 않는다.
- `split_policy=unseen_producer`는 학습/변환의 source P176 관계가 모두 알려져 있고 양쪽에
  겹치지 않아야 한다. 기존 family group 교차 금지도 유지한다. 이는 해당 snapshot의 명시 관계
  분리이지 실제 기업집단/위탁 생산/레시피 독립성의 보증이 아니다.
- fit은 지정 학습군만 사용하고 transform은 재학습하지 않는다. 원자 class/producer 토큰,
  unknown 수치·학습 범위/OOV·같은 score의 source ID 문자열순과 독립 사실 정답을 보존한다.
  source-ID 참고순은 Backend의 숫자 ID B0와 별개다.
- 보고서의 각 snapshot 해시/선택 revision, 모델 파라미터·전체 순위는 ignored다. macro 지표의
  양성 질의 수/생략 수뿐 아니라 변환 text zero/nonzero·관측 수치 개수도 함께 확인한다.
  양성1질의의 완전한 사실 검색을 전체 query/사용자 품질로 바꾸지 않는다.

```bash
uv run --locked python -m pubburi_recommendation.source_family_cohort \
  --manifest sources/wikidata-structured.json \
  --spec .pubburi/cohort-frozen-spec.json \
  --snapshot known .pubburi/a/entities.json .pubburi/a/receipt.json .pubburi/a/review.json \
  --snapshot unseen .pubburi/b/entities.json .pubburi/b/receipt.json .pubburi/b/review.json \
  --output .pubburi/cohort-new-report.json
```

새 private 출력만 허용하며 기존 결과는 읽기/fit 전에 보존한다. 원자 게시 함수와 고정 진단·
종료0=fit 계약 통과/1=계약 위반/2=입력·권리·출력 오류를 기존 실험과 공유한다.

## 실제 두 제조사의 상품군

이전 허용 snapshot2개에서 검수 상품군11개/명시 그룹11개·제조사 관계2개를 선택했다. raw/
revision과 기존 검수 hash를 다시 확인했고 source ID 중복/정규화 라벨 충돌은0이었다. 이것을
판매 SKU의 중복 부재라고 하지 않는다. 새 네트워크/브랜드 승격·업무 매핑은0이며 기존 별도
source-backed 업무 DEMO1 fit과 분리한다.

학습 전에 사실/분할/질의/정답·hash를 동결하고 한 제조사5개 fit·다른 제조사6개 transform을
실행했다. 실제5×7/rank5, 학습 도수5관측·용량0, 변환 도수/용량은 모두unknown이다.
미관측 제조사 한 곳의 상품군6개에서 producer 토큰은 모두OOV였고 class까지OOV인5개는 text zero vector였다.
공유 class가 있는1개만 지원했다. 수량·맛/향을 추정하거나 제조사 token을 임의 공통값으로
치환해 점수/커버리지를 만들지 않았다.

독립 exact-P31 사실 명세는 전체6질의·후보5 중 양성1질의만 Recall/NDCG를 계산하고 나머지5는
생략·원순위/동점을 보존했다. 클래스는 표현 입력이기도 해 사람 선호 정답과 독립적이지 않다.
표현 지원1/6과 지표 분모1을 함께 남긴 [실제 조건/원값](measurements/2026-11-02-cross-producer-cohort.md)을
따른다. 최종 holdout·서비스 SKU/추천 품질·다른 주종/기업 관계 일반화는 미완료이며 SVD를
fit/채택하지 않았다.

이 baseline은 그대로 유지하며 이후 [별도 고정 SVD 비교](measurements/2026-11-03-source-representation-comparison.md)에서
같은 원천/분할·전체 보고서를 재검증한 뒤 후보를 실제 fit했다. 원래 baseline의 SVD 미학습 상태와
별도 후보의 실행/운영 미채택을 구분하고 source 가족을 서비스 SKU로 승격하지 않는다.

## 다층 신경망 후보

같은 승인 snapshot과 상품군·제조사 분할을 사용해 TF-IDF 벡터를 복원하는 신경망을 실제 학습했다.
은닉층은 `8 → 2 → 8`이고, 가운데 2차원 임베딩의 양수 코사인으로 유사 후보를 비교한다.
tanh, L-BFGS, seed 0과 최대 1,000회 조건을 첫 학습 전에 고정했다. TF-IDF와 신경망은
학습군 5개에만 fit하며, 미관측 제조사 상품군 6개는 변환만 한다. 어휘가 전혀 겹치지 않는
입력은 신경망의 편향 때문에 유사 근거로 바뀌지 않도록 점수를 0으로 유지한다.

| 관측 | TF-IDF 기준 | 신경망 후보 |
|---|---:|---:|
| 학습 표현 크기 | 5 × 7 | 5 × 2 |
| 변환 질의에서 표현이 0인 수 | 5/6 | 5/6 |
| 양성 사실 질의 1개의 Recall/NDCG@1, @3 | 각각 1.0/1.0 | 각각 1.0/1.0 |

Python 3.12·scikit-learn 1.9.1에서 170회 최적화 후 수렴했다. 복원 RMSE는 학습군 5개에서
0.00327, 지원되는 변환군 1개에서 0.18829였다. 같은 입력으로 두 번 실행한 보고서는 바이트
단위로 일치했다. Recall/NDCG는 나머지 5개 질의에 양성 판단이 없어 생략했다. 정답과 표현이
같은 P31 분류 사실을 사용하고 지원 범위가 늘지 않아, 이번 결과로는 운영 채택이나 추천 품질
향상을 뒷받침할 수 없다.

위 cohort 예시에서 명령을 `uv run --locked python scripts/evaluate_neural_cohort.py`로 바꾸고
같은 manifest·spec·snapshot 입력과 새로운 ignored 출력 경로를 지정하면 재현할 수 있다.
실험 스크립트는 서비스 배포 패키지 밖에 두고 학습 데이터와 상세 보고서는 ignored에 보관한다.
모델 구성의 근거는 [다층 오토인코더 논문](https://pubmed.ncbi.nlm.nih.gov/16873662/)과
[MLPRegressor 공식 문서](https://scikit-learn.org/stable/modules/generated/sklearn.neural_network.MLPRegressor.html)다.
