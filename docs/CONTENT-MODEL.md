# B1 오프라인 상품 표현 fit

`content_model`은 상품 표현을 **실제로 fit하는 메모리 내 모듈**이다. 현재 HTTP API는 기존 B0와
health뿐이며 B1 서버 경로·모델 저장/로드·Backend 특성 API 연동은 아직 없다. 자동 수집·다운로드·
DB·외부 AI API 없이 직접 작성한 fixture로 fit/transform과 실패 경계를 실행한다.

실제 감사한 CC0 표본의 검수 판매 SKU는 여전히 0개다. 이 증가분은 모델 코드가 동작한다는
근거이며 서비스 카탈로그 학습·신규 상품 일반화 품질·AI03/DAT04 전체 완료를 뜻하지 않는다.
상품 표현 학습은 사용자 선호 학습이나 협업 필터링과 다르다.

## 입력과 담당 경계

- `ContentProduct`: B0의 `product_id/available/category/price_krw/abv_percent`에 `sku_group`,
  `taste_tags`, `aroma_tags`, `volume_ml`을 추가한다. 최대 1,000개·중복 ID 금지다.
- 태그는 각각 최대 20개·40자, trim/lowercase 뒤 중복을 거절한다. `null`은 미확인, `[]`는
  검수했지만 선언한 태그가 없다는 입력 의미를 보존한다. 둘 다 실제 맛/향 토큰을 만들지 않는다.
- 용량은 1–1,000,000mL 또는 unknown, 도수는 0–100% 또는 unknown이다. 가격은 필수 조건
  확인에만 쓰고 유사도 특성으로 학습하지 않는다. 시연 가격은 실제 판매가가 아니다.
- Backend F03의 `volumeMl/tasteTags/aromaTags`와 뜻·상한을 맞추지만 자동 매핑은 아직 없다.
  `sku_group`은 용량/도수 변형을 같은 상품군으로 검수해 분리하는 추천 실험 메타데이터다.
- 허용 여부가 확인된 주종/태그만 호출자가 제공한다. 타입 검증은 출처 권리를 승인하지 않는다.
  설명 원문·이름·URL·이미지·행동 로그·인기 통계는 이번 학습 입력에 없다. 허용 데이터 준비는
  [원천 감사](CATALOG-AUDIT.md)를 따르며 실제 입력/학습 산출물은 Git에 추가하지 않는다.

`ContentProfile`은 선호 주종/맛/향, 선택적인 선호 도수/용량을 받는다. 이 값들은 **soft preference**다.
예산·도수 범위·판매 상태·제외 ID 등 `Constraints`의 필수 조건은 유사도보다 먼저 적용한다.
`similar(reference, candidates)`는 선택 상품의 확인된 특성을 프로필로 사용하며 자기 ID를 제외한다.
자기 상품은 후보에서 분리하고 외부 제외 목록에 덧붙이지 않아 유효한 제외 ID 1,000개 상한을
보존한다. 후보의 크기/중복은 자기 상품을 제거하기 전에 검증하며 호출자의 제약을 변경하지 않는다.
장바구니 집계·다양성·피드백 저장/권한·필수 용량 조건은 이 증가분에 구현하지 않았다.

## 실제 fit과 점수

1. `FittedContentModel.fit(training_products)`는 학습 부분의 상품을 ID순으로 고정한다.
2. `category:값`, `taste:태그`, `aroma:태그`를 원자 토큰으로 만든다. callable analyzer를 사용해
   한국어 한 글자 `단`과 띄어쓰기 태그 `가벼운 질감`을 보존하고 맛/향의 같은 단어를 구분한다.
3. scikit-learn `TfidfVectorizer`가 vocabulary·smooth IDF를 실제 fit하고 L2 벡터를 만든다.
   변환 시 모르는 토큰은 어휘에 추가하지 않으며 응답의 known/OOV 개수로 한계를 드러낸다.
4. 도수·용량은 학습 부분의 **관측값만** 각각 `MinMaxScaler.fit`에 넣는다. 전부 unknown이거나
   관측 범위가 0인 열은 수치 점수에서 비활성화한다. 임의 단위의 거리나 가짜 0값을 만들지 않는다.
5. 요청에서 지원되는 텍스트·도수·용량을 활성 성분으로 정하고 같은 비중으로 평균한다.
   텍스트는 TF-IDF cosine, 수치는 `max(0, 1 - abs(target_scaled - actual_scaled))`다.
   수치 입력 자체는 clip하지 않아 학습 범위 밖 두 값이 끝점에 뭉쳐 동일해지는 것을 피한다.
   이 비중/거리는 초기 규칙이며 사용자 선호로 튜닝한 값이 아니다.
6. 상품의 unknown 수치 기여는 0이며, 그 상품만 분모를 줄여 유리하게 만들지 않는다.
   `contributions`는 실제 양의 내적 항/수치 기여만 반환한다. 합이 점수와 일치하고 0점 상품에는
   `content_similarity` 이유를 붙이지 않는다. 부동소수점 끝값은 [0,1]로 제한한다.
7. 점수 내림차순·동점 ID순서 뒤 limit을 적용한다. 필수 조건은 후보가 부족해도 완화하지 않는다.

빈 취향·미등록 어휘·활성 수치 없음은 `no_supported_preferences`, 지원 취향이 있지만 후보의
공유 특성이 전혀 없으면 `no_matching_features`와 B0 ID순서·0점을 반환한다. 후보 자체가 없으면
`no_eligible_products`다. 이는 로컬 엔진의 대체 동작이며 Backend의 서버 지연/장애 fallback은 별도다.
모델 fingerprint는 버전·학습 입력 해시·어휘/IDF·수치 fit 요약에 바인딩한다. 모델을 파일로 저장하거나
HTTP 프로세스 시작 때 불러오지 않는다.

## 고정 fit/transform 시연

~~~bash
uv run --locked python -m pubburi_recommendation.content_experiment \
  --spec evaluation/content-fit-v1.json \
  --output .pubburi/content-fit/run-1.json
~~~

CLI는 `authored_model_fixture`만 받는다. 제공자가 검수하지 않은 실제 데이터를 fixture로 재분류하면
안 된다. 현재 명세는 직접 만든 허구 상품·태그·시연 가격이며 실제 주류 사실/사람의 취향 정답이 아니다.
출력은 ignored `.pubburi`/`reports`에 새 파일만 만들고 기존 파일을 보존한다. 원문 JSON은
10MiB 상한·중복 키/비유한 수치 거절을 적용한다. 종료값은 계약 통과 0, 위반 1, 입력/출력 실패 2다.

- 학습 4행/3상품군과 변환 7행/6상품군을 **명시 분리**한다. 변형 ID가 달라도 같은 `sku_group`은
  경계를 넘지 못하며 미지정/중복/교차 그룹·학습군 후보를 거절한다.
- 이 분할 검증은 실험 명세가 수행한다. Python `fit(list)` 자체는 호출자가 전달한 부분만
  학습하므로 서비스/다른 실험 호출자는 목적에 맞는 분할·권리 검수를 별도로 보장해야 한다.
  알려진 카탈로그 검색과 신규 상품 평가를 같은 조건으로 간주하지 않는다.
- 변환에만 있는 `신규 태그`·도수100·용량1이 학습 vocabulary/범위에 섞이지 않는지 확인한다.
  이 분할은 누수 방지 코드의 회귀이며 실제 신규 상품의 최종 holdout이 아니다.
- 수동 선언한 적격 후보와 독립 조건 검사로 필수/제외·결측·중복·카디널리티를 확인한다. 선택 상품,
  빈 취향·OOV·실제 0·미확인 수치·빈 후보를 포함하며 점수 함수로 관련성 정답을 생성하지 않는다.
- 같은 조건의 B0/B1 ID/실제 점수·기여를 기록한다. 시연에서 순서가 달라졌다는 사실은 품질 개선이
  아니다. Recall/NDCG는 독립 관련성 라벨이 없어서 미산출한다. 최종 평가·성능·만족도 수치도 없다.

`scripts/evaluate_content.py`와 필수 CI는 실제 fixture fit을 실행하고 입력/응답/어휘/IDF가 없는 요약만
7일 보관한다. 새 wheel은 checkout 밖 runtime-only `python -I`로 같은 CLI fit을 실제 실행한다.
기존 B0 ASGI 계약과 실제 health/B0/OpenAPI HTTP 배포 검증도 유지한다. [테스트 안내](TESTING.md).

## 후속 작업과 공식 근거

검수 서비스 SKU 확보·실제 source-to-feature 매핑, 관련성 명세·개발/검증/최종 평가와 신규 상품
평가, B1 HTTP·버전별 준비 상태/장애 계약·Backend/Frontend 연동은 남아 있다. TruncatedSVD는 현재의
작은 회귀 fixture로 채택하거나 기각하지 않았고, 충분한 실카탈로그 차원/다양성에서 비교한다.

2026-11-01 확인한 [TF-IDF analyzer/IDF/L2](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html),
[MinMax fit/transform](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.MinMaxScaler.html),
[학습 부분 전처리·누수 방지](https://scikit-learn.org/stable/common_pitfalls.html)를 근거로 선택했다.
[공식 배포 정보](https://pypi.org/project/scikit-learn/)의 Python/NumPy/SciPy 요구사항·BSD 조건을
확인하고 scikit-learn·직접 사용하는 NumPy 및 전이 runtime 의존성을 `uv.lock`에 고정했다.
의존성 증가와 로컬 fit 비용은 별도 부담이며 지연 개선을 주장하지 않는다.
