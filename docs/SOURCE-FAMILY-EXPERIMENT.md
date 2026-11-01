# 검수 원천 상품군의 오프라인 표현 학습

`source_family_experiment`는 **source QID 기반 상품군 표현 실험**이다. 기존 B1의 서비스 SKU
`ContentProduct`·HTTP·Backend 상품 ID·추천 순위를 변경하거나 새 서비스 랭커를 만들지 않는다.
권리·정체성을 검수한 실제 구조화 자료를 사용자/행동 로그 없이 학습할 수 있지만, 이 실행이
판매 SKU 카탈로그·서비스 B1 학습·추천 관련성·사용자 만족도 평가 완료를 뜻하지는 않는다.

## 입력 승인과 동결

- 지원 원천은 기존 `wikidata-structured`/CC0다. SourceManifest의 normalization과
  `structured_feature_fit`가 모두 승인된 범위만 사용하며 미승인은 원본을 읽기 전에 보류한다.
- 원문·검수 mapping·수집 receipt·원천 manifest의 파일 SHA-256을 명세에 고정한다.
  receipt의 manifest 해시는 검증된 manifest 모델의 직렬화 해시이므로 파일 바이트 해시와
  별도로 대조한다. accepted/error·live/offline·정확 ID/revision과 기존 API 오류 경계도 재확인한다.
- 선택한 각 항목은 이름이 있는 `product_family`로 명시 검수돼야 한다. 브랜드·생산자·주종을
  실험 명세에서 상품군으로 바꾸거나 source QID를 Backend의 숫자 상품 ID로 만들지 않는다.
- 학습 전 명세에 `family_groups`, 서로 겹치지 않는 fit/transform 그룹과 전체 선택 항목의
  수동 사실 명세를 고정한다. P31/P176·관측 도수/용량을 원문 감사 결과와 대조하고 모순은 거절한다.
  자동 점수나 모델 결과로 사실 기대값·관련성 정답을 생성하지 않는다.
- `evidence_kind`는 실제 검수 원천과 `authored_regression_fixture`를 구분한다. CI는 직접 쓴
  허구 항목만 사용하고 실제 원문·개별 카탈로그·학습 파라미터를 Git/CI artifact에 올리지 않는다.

## 학습·변환과 검사

1. fit 그룹의 항목만 source ID순으로 정렬한다. `instance_of:QID`, `producer:QID`를 서로 다른
   원자 토큰으로 만들어 TF-IDF vocabulary·smooth IDF·L2 표현을 실제 fit한다. 이름·설명·이미지·
   맛/향 추정·가격·평점·인기/행동은 입력하지 않는다. 동일한 클래스 ID만 같은 특성으로 취급하며
   주종 계층이나 언어적 의미를 자동 학습한 것으로 해석하지 않는다.
2. 도수·용량은 각각 fit 부분의 관측값에만 MinMaxScaler를 fit한다. 관측0개인 열은 all_unknown,
   상수 열은 constant로 비활성화한다. 미확인 값은 관측0으로 바꾸지 않는다.
3. transform 부분은 fit하지 않는다. 모르는 토큰/OOV·벡터 norm·수치 관측 여부/지원 여부를
   기록하고 학습 범위 밖 값은 clip하지 않고 표시한다. 미지원/unknown의 scaled_value는 null이다.
4. 동결한 학습 사실로 별도 계산한 vocabulary/DF-IDF·수치 범위를 실제 학습 상태와 대조한다.
   fit fingerprint는 학습 사실·파라미터·알고리즘/라이브러리 버전에만 결속된다. 전체 실험의
   원천/명세 해시와 분리하므로 held-out 사실 변경이 fit 상태를 바꾸지 않는지 확인할 수 있다.
5. 희소 행렬의 차원과 작은 행렬의 실제 rank를 기록한다. dense 검사는 1,000,000셀 이내로
   제한하고 그 밖에는 rank 상한만 남긴다. 이번 실험은 SVD를 fit하지 않으며 충분한 카탈로그와
   목적별 평가 근거 없이 복잡한 표현을 채택하지 않는다.

보고서에는 학습 파라미터가 있으므로 `.pubburi` 안의 새 파일만 허용한다. 임시 파일에 완전히 쓴
뒤 hard link로 원자 게시하며 기존/경쟁 생성 파일은 덮어쓰지 않는다. 실패한 임시 파라미터는 정리한다.
종료값은 계약 통과0·학습 상태 검사 실패1·입력/권리/출력 실패2다. 진단에는 원문·개인 경로를 넣지 않는다.

~~~bash
uv run --locked python -m pubburi_recommendation.source_family_experiment \
  --manifest sources/wikidata-structured.json \
  --input .pubburi/entity-catalog/h7-named-beer-default-labels-live/entities.json \
  --receipt .pubburi/entity-catalog/h7-named-beer-default-labels-live/receipt.json \
  --review .pubburi/entity-catalog/h7-named-beer-default-labels-review.json \
  --spec .pubburi/source-family-experiment/h8-frozen-spec-v2.json \
  --output .pubburi/source-family-experiment/new-fit-report.json
~~~

## 실제 첫 실행과 남은 범위

[고정 원천 실험 기록](measurements/2026-11-01-source-family-fit.md)은 실제 CC0 상품군5개를
3개 학습/2개 변환으로 나눠 실행했다. TF-IDF 3×5·rank3, 학습 도수3관측·용량0관측을 확인했다.
두 변환 항목은 각각 주종 토큰이 OOV라 공통 제조사 토큰만 남았다. 이는 실제 표현의 제한을
드러낸 결과이며 신규 상품 추천 품질이 검증됐다는 뜻이 아니다.

독립 관련성 라벨이 없어서 Recall/NDCG는 미산출이다. 최종 holdout·사람 선호·서비스 모델 평가,
판매 SKU/포장·용량·상품군 대응과 서버/웹 연동은 남아 있다. 공식 근거는
[Wikidata 구조화 CC0](https://www.wikidata.org/wiki/Wikidata:Licensing),
[TF-IDF](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html),
[MinMaxScaler](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.MinMaxScaler.html),
[학습 전처리 분리](https://scikit-learn.org/stable/common_pitfalls.html)다.
