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

## 선택적인 고정 사실 검색 평가

`retrieval_cases`가 없는 기존 명세는 관련성 지표를 계산하지 않는다. 이를 명시한 경우에도
모델/점수 튜닝 전에 case ID·변환 질의 ID·학습 후보 ID·양성 ID·cutoff·사실 판단 근거를 고정한다.
질의는 transform 그룹, 후보는 fit 그룹이어야 하며 질의 자신이나 다른 held-out 후보를 넣지 않는다.
수동 양성/음성 선언은 원천의 **정확 P31 교집합**과 대조한다. 결과 score에서 정답을 만들지 않는다.
클래스는 표현의 입력 특성이기도 하므로 이 검사는 사실 검색 관련성이고 독립 사람 선호/의미
유사도 정답이 아니다. 주종 계층·맛/향·다른 표현으로 정답 범위를 확대하지 않는다.

기존 fit된 vocabulary/IDF만으로 질의를 transform하고 학습 후보와 L2 텍스트 벡터의 내적
(cosine)을 계산한다. 관측 수치/서비스 점수 함수를 새로 결합하지 않는다. 같은 score는 source ID
문자열순으로 정렬한다. 비교 참고순도 같은 source ID 문자열순이며 기존 source 실험의 고정 ID
순서를 대조군으로 사용한다. 유리한 순서를 사후 선택하거나 실제 서비스 기준 모델로 포장하지 않는다.
이 참고순은 숫자 업무 ID를 사용하는 Backend/B0 API와 별개이고 사용자에게 제공되는 랭커가 아니다.

[독립 검사기](../src/pubburi_recommendation/source_family_evaluation.py)는 모델 fit/순위를 실행하지
않고 결과 후보 전체·중복/누락·유한 score/동점 순서를 확인한 뒤 동결된 양성 집합으로 이진
Recall@k·NDCG@k를 계산한다. Recall 분모는 선언 양성 수, ideal DCG는 min(k, 양성 수)이며
0양성 질의는 두 지표를 생략한다. macro 평균은 cutoff별 실제 양성 질의 수와 제외 수를 함께
기록한다. 완전한 원순위/score·양성0 질의의 OOV/동점 결과도 private 보고서에 남긴다.

## 실제 새 상품군과 작은 사실 평가

2026-11-01의 [추가 원천/평가 기록](measurements/2026-11-01-source-family-fact-evaluation.md)은
새 실명 상품군6개를 각각 다른 그룹으로 검수해4fit/2transform을 실행했다. 같은 원천 스타일을
공유하는 서로 다른2개 상품군 중1개를 변환에 두고, 또 다른 변환 상품군은 미관측 스타일로
선택했다. 양성1질의/후보4와 양성0질의1을 사전 고정한 목적 표본이며 무작위/대표 표본이 아니다.
이 새6개는 같은 제조사여서 제조사 간 일반화를 평가하지 않는다.

다음 [미관측 제조사 cohort](SOURCE-FAMILY-COHORT.md)는 별도 두 accepted snapshot을 각각
검증해11상품군/2제조사를 연결한다. 이 단일 snapshot 계약을 유지하며 같은 fit/평가기를 재사용한다.

TF-IDF4×5/rank4와 학습 부분만의 어휘/IDF를 확인했다. 도수는 source 단위가 공식 P2665의
허용 volume-percent와 달랐고 용량은 포장별 qualifier가 있어 둘 다 unknown으로 보존했다.
0–100 범위나 다른 웹페이지의 숫자만 보고 단위를 바꾸거나330mL와20L를 하나로 고르지 않았다.
양성 질의의 관련 상품은 참고순3위·cosine1위였고, 미관측 스타일 질의는 공통 제조사만 남아
동점이었다. 표본1의 사실 검색 결과를 서비스 순위 개선·사용자 만족·신규 SKU 일반화/최종
평가로 표시하지 않는다. 이번 서비스 신규 매핑은0이며 기존 별도 업무 DEMO1 fit과 구분한다.

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
