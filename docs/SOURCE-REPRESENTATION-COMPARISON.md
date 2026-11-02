# 고정 원천 상품군의 TF-IDF/SVD 표현 비교

`source_representation_comparison`은 기존 검수 상품군 cohort와 **같은 전체 B1 보고서**를
재계산한 뒤, 사전 고정한 TF-IDF + TruncatedSVD 후보를 실제 fit/transform한다. 기존 실험의
`svd.fitted=false`는 B1 자체의 상태로 보존하고 별도 `candidate`에만 SVD 결과를 둔다.
새 서비스 랭커·HTTP·상주 모델·업무 SKU 매핑을 만들지 않는다.

## 고정 프로토콜과 입력

기존 [cohort 명세](SOURCE-FAMILY-COHORT.md)는 원천별 accepted receipt/raw/review·manifest
해시와 명시 상품군·제조사 분리/사실 질의를 계속 소유한다. 별도 comparison 명세는 아래를
**첫 후보 fit 전에** 고정하며, 실제 원본/모델 파라미터는 ignored에만 저장한다.

- 원래 cohort 명세·전체 baseline 보고서의 SHA-256, baseline fingerprint, 자료 성격과
  explicit UTC 동결 시각. 파일 hash뿐 아니라 현재 원천으로 재계산한 baseline 전체 내용도
  기존 보고서와 정확히 같아야 한다. 원천/review/receipt 변경은 기존 검증을 통과해야 한다.
- 설치된 sklearn 버전, `algorithm=randomized`, n_components/random_state/n_iter/
  n_oversamples, `power_iteration_normalizer=QR`, `l2_tfidf_then_l2_latent`.
  이 도구는 명시한 단일 후보만 실행하며 결과를 보고 차원/seed를 자동 탐색하지 않는다.
- 기존 모든 retrieval case ID와 순서, 학습 재구성 상대 오차·비중심 에너지 보존 비율·중심화
  설명분산 비율, 변환 영벡터/OOV와 같은 동결 사실 검색의 전체 순위/지표 분모를 고정한다.
- 최소한 실제 rank 감소가 있어야 한다. `n_components`는 학습 행/열 중 작은 값과 실제 rank보다
  작아야 하며, 밀집 재구성 검사를 위해 학습 행×열을1,000,000 이하로 제한한다. 무어휘/상수
  rank1/미확정 rank·억지로 원차원까지 늘리는 후보는 fit 전에 거절한다.

```bash
uv run --locked python -m pubburi_recommendation.source_representation_comparison \
  --manifest sources/wikidata-structured.json \
  --spec .pubburi/cohort-frozen-spec.json \
  --baseline-report .pubburi/cohort-baseline.json \
  --comparison-spec .pubburi/comparison-frozen-spec.json \
  --snapshot known .pubburi/a/entities.json .pubburi/a/receipt.json .pubburi/a/review.json \
  --snapshot unseen .pubburi/b/entities.json .pubburi/b/receipt.json .pubburi/b/review.json \
  --output .pubburi/comparison-new.json
```

출력은 새 `.pubburi` 파일에만 원자 발행하고 기존 파일은 원천 읽기/fit 전에 보존한다.
종료0은 실행/기존 fit 계약 통과,1은 기존 계약 위반,2는 입력/authority/실행 실패다.
입력 오류에는 개인 경로·원문·모델 파라미터를 반사하지 않는다. 종료0이 모델 채택/품질 승인은 아니다.

## fit/transform과 측정의 뜻

기존 B1은 그대로 실행하고, 비교 후보도 **학습 상품군만**으로 같은 원자 class/producer 토큰의
TF-IDF vocabulary/IDF를 fit한다. 학습 어휘·IDF·행렬 shape가 baseline과 일치해야 SVD를 fit한다.
기존 MinMax 수치 fit과 unknown/변환 결과는 그대로 보존하며 SVD에는 수치 열을 합치지 않는다.
변환 상품군은 이 어휘와 이미 fit한 SVD를 transform만 한다. 이름/태그·맛·가격·정답 라벨로
새 특성을 만들지 않으며, 변환 어휘/수량 변화가 후보 fit 파라미터·fingerprint를 바꾸면 안 된다.

학습 TF-IDF 행렬을 X, SVD의 정규화 전 좌표를 Z, 역변환을 X̂라고 할 때 다음을 구분한다.

| 측정 | 분자/분모와 해석 |
|---|---|
| reconstruction_relative_frobenius_error | ‖X−X̂‖F / ‖X‖F. 학습 표현의 상대 재구성 오차 |
| retained_frobenius_energy_ratio | ‖X̂‖F² / ‖X‖F². 비중심 학습 에너지 보존 비율 |
| explained_variance_ratio / sum | sklearn이 계산한 각 축/전체 중심화 분산 비율. 위 에너지 비율과 분모가 다름 |
| source/latent zero 및 OOV | 변환 입력의 어휘 미지원과 투영 뒤 실제 지원 범위. 결측을 새 스타일로 표시하지 않음 |
| 같은 frozen 사실 Recall/NDCG | 기존 exact-class 정답·fit 후보·cutoff의 순위 검사. 사용자 선호/서비스 품질이 아님 |

재구성은 Z를 정규화하기 **전**에 계산한다. 사실 검색에서만 Z의 각 행을 L2 정규화해 cosine을
계산한다. latent cosine은 음수일 수 있어 별도 signed 검사를 사용하며, 음수를0으로 자르거나
확률처럼 이동하지 않는다. 기존 비음수 TF-IDF 검사 기본 계약은 유지한다. OOV 영벡터의0점
동점·source ID순 원순위와 양성 없는 질의의 지표 생략/전체 분모를 보존한다.

[TruncatedSVD 공식 문서](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.TruncatedSVD.html)의
비중심 희소행렬 처리·고정 난수/반복 설정과 설명분산 정의를 따르고,
[L2 normalize](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.normalize.html)를
검색 좌표에 적용한다. [전처리 누수 지침](https://scikit-learn.org/stable/common_pitfalls.html)에 따라
변환 자료를 fit에 넣지 않는다. 같은 seed도 라이브러리/수치 환경의 모든 버전에서 같은 행렬을
보장하는 것은 아니므로 버전과 실제 재현 결과를 함께 기록한다.

## 실제 판단과 남은 조건

기존11상품군의5fit×7/rank5·6transform에서 고정2차원 후보를 실행했다. 학습 에너지 보존
51.10%·재구성 오차0.6993·설명분산 합26.72%였고, 변환 영벡터5/6은 그대로였다. 기존 양성
1질의의 사실 순위 지표도 같아 새 지원 범위/독립 관련성 근거가 늘지 않았다. [실제 원값/동결/
한계](measurements/2026-11-03-source-representation-comparison.md)를 따른다.

이번 후보는 운영에 채택하지 않는다. 작은 목적 표본에서 정보 손실이 있고 OOV 지원은 늘지
않으며, 사실 정답이 입력 class와 공유돼 서비스 적합성을 판단할 독립 증거가 부족하다. 다른
차원/seed를 이 변환 질의에 맞춰 튜닝하지 않는다. 지연/메모리는 측정하지 않아 성능 개선/회귀를
주장하지 않는다. 실제 서비스 DEMO1상품·완성 SKU/업무 매핑·서비스 B1/일반화·최종 품질과
전체 AI03/DAT02–04는 여전히 미완료다. 이를 사용자/미래 로그 부재 때문에 대기시키지 않는다.
