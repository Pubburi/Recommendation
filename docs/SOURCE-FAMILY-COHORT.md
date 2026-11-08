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

## aT 전통주로 확대한 B1·D1 비교

공공 CSV 1,251행 중 누적 115개 원천 행을 같은 제공자의 공식 자료와 대조하고 확인한 사실만
사용했다. 판매 SKU 수가 아니다. 이름/제조사·변형·단위·정체성이 모호한 필드는 보류하며 가격·
맛·향을 추정하지 않는다. 변경금지 조건이 명시된 별도 게시물은 새 정제·학습·정답에서 보류하고
다른 자료의 허용 사실까지 일괄 차단하지 않는다. 원문/이미지·개별 원료 라벨을 Git에 배포하지 않는다.
[aT 공공 CSV](https://www.data.go.kr/data/15048755/fileData.do) ·
[공식 감 자료](https://thesool.com/front/publication/M000000066/view.do?bbsId=A000000044&publicationId=C000002670) ·
[공식 커피 자료](https://thesool.com/front/publication/M000000066/view.do?bbsId=A000000044&publicationId=C000002727)

원문·검수·제조사 별칭 그룹·분할·원료 정답은 fit 전에 고정한다. 정답은 직접 명시된 발효
기초 재료의 일치이며 물/발효제·비주원료 첨가물은 제외한다. 쌀 품종은 쌀로 묶고 쌀+단호박은
쌀 단독과 구분한다. 원료는 fit/점수에 넣지 않는다. 명시된 일반증류주는 기존 넓은 증류주로
투영하고 두 비교에 같은 사실을 사용한다. 제조사 분리는 수동 별칭 검수 기준이지 실제
기업집단·물리 SKU 독립성의 보증이 아니다.

B1은 학습 행의 주종 TF-IDF·관측 수치/마스크만 fit한다. D1은 같은 표현을 복원하는
기본 `8 → 2 → 8` 신경망이며 개발 후보로 `8 → 4 → 8`도 비교한다. tanh·L-BFGS·seed0·
최대1,000회는 유지하고 범위 밖 수치 변환은
0–1로 제한한다. B1의 양수 후보 안에서만 B1과 양수 잠재 코사인을 섞어 재정렬한다.
후보·필수/제외 조건을 넓히지 않는다. 양성 없는 질의는 순위를 보존하고 지표 평균에서 제외한다.

| 고정 비교 | 양성 질의/전체 | B1 Recall@3 | D1 Recall@3 | B1 NDCG@3 | D1 NDCG@3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 최초 15학습·16최종, 가중치 0.5 | 14/16 | 0.6548 | 0.6548 | 0.7584 | 0.7417 |
| 같은 15학습·새 6튜닝, 가중치 0.75 | 4/6 | 0.5833 | 0.5833 | 0.5000 | 0.5433 |
| 같은 15학습·새 6최종, 가중치 0.75 | 4/6 | 0.3333 | 0.3333 | 0.4260 | 0.4106 |
| 새 4학습·3최종, 가중치 0.25 | 2/3 | 0 | 0 | 0 | 0 |
| 원 15+새 4학습·3개발 튜닝, 가중치 0.25 | 2/3 | 1 | 1 | 1 | 1 |
| 같은 19학습·새 8최종, 가중치 0.25 | 6/8 | 0.5000 | 0.5333 | 0.8333 | 0.9013 |
| 같은 19학습·다음 7최종, 가중치 0.25 | 7/7 | 0.6429 | 0.7857 | 0.4587 | 0.5714 |
| 확장 24학습·같은 7최종, 가중치 0.25 | 7/7 | 0.7857 | 0.7143 | 0.6088 | 0.5536 |
| 같은 24학습·개발군 선택 후 새 6최종, 가중치 0.25 | 4/6 | 0.2500 | 0.2500 | 0.1577 | 0.1577 |
| 확장 32학습·관측 마스크 개발 선택 후 새 5최종, 가중치 0.25 | 5/5 | 0.6000 | 0.6000 | 0.5066 | 0.5066 |
| 확장 36학습·denoising 개발 선택 후 새 7최종, 가중치 0.25 | 5/7 | 0.4500 | 0.4500 | 0.5654 | 0.5654 |

최초 15학습의 가중치는0.5이며 다음6튜닝은 사전0.25/0.5/0.75 중 NDCG 최대·동률 낮은
가중치를 선택했다. 새4학습의135회 수렴 경고·최종0, 원19학습의541회 수렴, 확장24학습의
519회 수렴과 해당 고정 최종의 정확 반복을 보존한다. 같은7최종에서 학습 확대가 D1 우위를
보장하지 않았다. CSV `0.07`과 공식 `7%`를 자동 환산하지 않고, 포장 불일치/여러 용량은
unknown이다. 자세한 과거 분할·누락·선택은 [고정 이력](https://github.com/Pubburi/Recommendation/blob/7296b777951d793db9406a64b88e04cc9ec09e51/docs/SOURCE-FAMILY-COHORT.md)에 보존한다.

24학습의2/4차원 개발 NDCG는 모두0.5655라 사전 동률 규칙으로2를 선택했다. 낮은 학습
복원 RMSE(0.07434/0.03916)를 관련성으로 바꾸지 않았고 미선택4의 최종은 실행하지 않았다.
32학습의 관측 flag 크기1/0.5도 개발 동률로1을 선택했다. 입력과 target을 함께 변환한 실험이며,
역변환한 원래 인코딩 RMSE는0.06108/0.08597, 축소 target 오차는0.06108/0.06021이다.
두 후보 모두 최대1,000회 수렴 경고를 보존했고 미선택0.5의 최종은 실행하지 않았다.

새 검수15행은 **4학습·4개발·7최종**으로 점수 관측 전에 분리했다. 새 공식6문서 중 제조사
문맥/variant가 불명인 자료는 보류하고 허용된 기존 캐시 근거2건도 원 capture 그대로 재검수했다.
새 학습의 주종 충돌1행과 도수 충돌1행은 해당 필드만 unknown이며, 원료 표가 모순인1행은
원료 정답에 쓰지 않았다. 36학습/34생산자·10특성의 도수는34관측/2누락·3–47%, 용량은
14관측/22누락·200–1,000mL다. 개발은 쌀2·혼합2로 양성2/전체4, 최종은 쌀5·쌀+무화과1·
포도1로 양성5/전체7이다. 비쌀 양성 질의가 없어 일반화 범위가 좁다.

[denoising 연구](https://jmlr.org/papers/v11/vincent10a.html)의 손상 입력→원 입력 복원 개념에서
train-only 수치 블록 후보를 만들었다. 해당 논문의 stacked 구조/분류 성과를 재현한 주장은
아니다. 원 학습행과 관측된 수치 블록 하나의 값+flag만 함께 가린 결정적 view를 사용하고,
target은 원래 관측행렬이다. unknown 블록과 무근거 영입력은 새 손상 view를 만들지 않는다.
원천 값을 복원 결과로 채우지 않고 미관측 상품은 기존 사실로 변환만 한다. view당 같은 학습
가중치이므로 관측 블록 수가 많은 상품의 학습 비중도 달라지며, 이를 사람의 선호로 해석하지 않는다.
2차원·seed0·alpha0.001·관측 크기1·잠재 가중치0.25와 다른 설정은 고정했다.

| 새 개발 양성2/전체4 | clean | 수치 블록 denoising |
| --- | ---: | ---: |
| 실제 학습 상품 / 학습 view | 36 / 36 | 36 / 84 |
| 카탈로그 사실 NDCG@3 | 0.5655 | 0.5655 |
| 원 clean 인코딩 행렬 복원 RMSE | 0.07777 | 0.12672 |
| 각 학습 target의 objective RMSE | 0.07777 | 0.12030 |

추가48view는 합성 학습 입력이며 신규 관측 상품이 아니다. 서로 다른 target/분모의 objective
오차를 직접 개선율로 비교하지 않는다. 두 모델은 최대1,000회 수렴 경고가 났다. 개발 NDCG 최대·
동률 clean의 사전 규칙으로 clean을 선택한 뒤에만 새 최종을 열었다. 미선택 denoising의 최종은
실행하지 않았다. 최종은 B1과 선택 clean의0상승·5동률·0하락, 빈 순위1/전체7이며 양성 없는
2질의의 순위도 보존했다. 바이트 동일 반복과 독립 Recall/DCG 재계산을 확인했고, 원32학습의
기본 clean fit fingerprint도 유지했다. 비수렴·관련성 동률 때문에 서비스 채택 근거를 충족하지 못했다.

**서비스는 B1을 유지한다.** 작은 원천 사실 비교이며 사람의 선호·서비스 품질·지연 개선은
아니다. 더 많은 데이터나 낮은 복원 오차가 관련성 우위를 보장하지 않았다. 업무 ID/현재 사실·
실제 기여 이유·신규/장애 fallback·동일조건 지연은 별도 채택 게이트다. 다음 개발에는 검수36
학습만 재사용하고 노출 평가79행/생산자는 fit/튜닝에서 제외해 새 개발/최종을 고정한다.
알려진 원천 용량을 기존 family DEMO/업무 export·HTTP로 자동 승격하지 않는다.

`uv run --locked python -m scripts.evaluate_neural_heldout`에 manifest, CSV, 원 receipt,
review, 고정 protocol, 근거 파일과 새 ignored 출력 경로를 전달한다. `--latent-weight`는
유한 0–1, 기본0.5다. `--bottleneck-dimension`은 정수2/4만 받고 기본2를 유지한다. encoder는
실제 학습된 차원을 사용하며 무근거/OOV 영입력을 편향만으로 양수 근거로 바꾸지 않는다.
`--observation-scale`은 유한1/0.5만 받으며 기본1의 과거 fit을 보존한다. 알려진 수치0과
unknown의 flag 차이는 유지하며 B1 fit/양수 후보·제약을 바꾸지 않는다.
`--training-mode`는 `clean`(기본)/`numeric-block-denoising`만 받으며, 기본값은 과거 fit을
보존한다. 보고서의 실제 상품 수·증강 view 수와 clean 복원/각 target 오차를 분리한다.
정책 재검수는 원 CSV/receipt 바이트·획득 시각을 바꾸지 않고 새 review에 결속한다. 과거43행은
당시 고정 코드(`4f87ea3`)·manifest로 재현한다. 원문/개별 순위/모델은 ignored이며 실험
스크립트는 서비스 wheel 밖에 둔다.
