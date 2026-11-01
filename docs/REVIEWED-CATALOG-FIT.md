# 검수 업무 카탈로그의 실제 B1 fit과 고정 사실 검사

`python -m pubburi_recommendation.reviewed_catalog_fit`는 기존 원천/업무 검수 파이프라인을
통과한 카탈로그에 **기존 FittedContentModel**을 실제 fit하고 B0와 같은 후보/조건에서
동결된 사실 시나리오를 검사한다. 새로운 추천 점수 알고리즘·서비스 상주 모델을 만들지 않는다.

## 명세와 실행

실제 fit 전에 `source_catalog_sha256`, UTC 동결 시각, 원천 문자열 key별 기대 상품 사실과
시나리오를 파일로 고정한다. 기대값은 모델의 순위/점수로 생성하지 않는다. 검수 매핑의 명시
업무 ID로만 key를 해석하고 다음을 fit 전에 확인한다.

- [검수 원천](SOURCE-CATALOG.md)·[업무 스냅샷/매핑](BUSINESS-EXPORT.md)을 다시 검증한다.
  `existing_local_catalog`에는 허구가 아닌 원천 사실을 전용 업무 DEMO로 등록한 경우도 포함한다.
  이는 수집자의 기록이며 실판매·재고·트랜잭션/서버 revision의 보증은 아니다.
- 기대 facts가 정확히 매핑된 상품을 덮고 도수/용량·주종·시연 가격·그룹·가용성과 null/[]가
  일치해야 한다. 미래 동결 시각·변경 hash·불명/중복 key·직접 추정한 업무 ID·모순된 제약은 거절한다.
- 시나리오의 통과 key/결과 개수·조건·제외·fallback은 수동 선언한다. 별도 요구사항 검사기
  `scenario_evaluation.eligibility_issues`로 이 선언과 사실의 모순을 확인하고 모델 결과와 비교한다.
  생산용 filter/score helper를 기대값 생성에 쓰지 않으며 DTO는 공유한다.
- fit 뒤 B0의 ID순/개수·fallback, 두 결과의 후보/중복/필수 조건/이유·개수, B1의 선언된
  fallback·실제 특성/프로필에 있는 기여와 score 합을 검사한다. 순위 관련성 정답은 아니다.

```bash
uv run --locked python -m pubburi_recommendation.reviewed_catalog_fit \
  --manifest sources/wikidata-structured.json \
  --input .pubburi/source/entities.json \
  --source-receipt .pubburi/source/receipt.json \
  --curation .pubburi/catalog-curation.json \
  --business-snapshot .pubburi/business-snapshot.json \
  --mapping .pubburi/reviewed-mapping.json \
  --spec .pubburi/frozen-facts.json \
  --output-dir .pubburi/reviewed-fit-new
```

새 ignored 폴더만 허용하고 기존 결과는 원천 읽기/재학습 전에 거절한다. `fit-report.json`은
명세/원천/업무/매핑 hash, fit 요약·어휘/IDF·시나리오별 원결과와 한계를 보관한다.
`receipt.completed`는 기록 완료, `passed`는 해당 사실 검사의 통과이며 둘을 구분한다.
종료 코드는0=검사 통과,1=검사 위반,2=입력/해시/실행 오류다. 원문·전체 보고서/모델 파라미터는
Git/CI artifact에 넣지 않는다. 서버 시작·health·B0에는 fit/DB/외부 키가 추가되지 않는다.

## 실제 원천 기반 업무 DEMO 증가분

2026-11-01 허용 [CC0 구조화 원천](https://www.wikidata.org/wiki/Wikidata:Licensing)의
검수 포장 후보1개를 root가 전용 폐기 DB의 업무 API로 등록했다. 기존 사용자 DB/기존80상품을
변경하거나 모델 입력에 합치지 않았다. CC0 이름·도수/용량과 수동 업무 분류, 명시 DEMO가격·
일반 placeholder 파일명을 구분했고 원천 이미지/본문·맛/향·제조사/묶음수를 가져오지 않았다.
API가 반환한 업무 ID와 fresh snapshot으로 명시 매핑1개·B0/B1 export1개를 확인했다.

실제 fit 전에 동결한9개 조건은 cold start·업무 주종 취향·도수 경계 포함/미달·DEMO가격
상한 미달·다른 필수 주종·명시 제외·미관측 맛 OOV·상수 수량 프로필이다. B0/B1의 같은
후보/조건에서 모두 사실/계약 검사를 통과했다. 이것은 관련성 정확도9/9나 사람의 선호 성과가 아니다.

실제 fit은1상품/1그룹이다. TF-IDF는 업무 분류 `category:맥주`1어휘/IDF1을 학습했다.
원천 도수/용량의 수치 변환은 각각 관측1개·범위5–5vol%/500–500mL이며 상수라 활성 거리
특성은0개다. 미확인 맛/향은 각각1/1 null, 검수된 빈 태그는0이다. OOV·빈 취향과 상수
수량만 요청한 경우 결정적 기본순을 유지했다. 자세한 [조건/원값](measurements/2026-11-01-reviewed-catalog-fit.md)을 따른다.

같은 데이터/모델에서 순위 개선을 판별할 비교 후보가 없고, 학습/평가 상품군 분리·신규상품
일반화·독립 관련성 라벨·최종 holdout도 없다. Recall/NDCG는 미산출이며 SVD/복잡한 모델을
억지로 적용하지 않았다. 서비스 카탈로그 전체 준비/품질·Backend의 B1 자동 호출이나 학습된
모델 배포를 완료한 것이 아니다. 명시 fit의 첫 실제 데이터 증가분과 전체 AI03 완료를 구분한다.

[구현](../src/pubburi_recommendation/reviewed_catalog_fit.py) ·
[직접 작성 회귀](../tests/test_reviewed_catalog_fit.py) ·
[작업/인계](plans/2026-11-01-reviewed-catalog-fit.md)
