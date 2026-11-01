# B1을 재사용하는 별도 탐색 후보

## 범위와 사전 조건

R08의 추천 소유 기술 증분으로 새 opt-in `/v1/recommendations/exploration`만 추가한다. 기존 B0/content
기본 계약·모델·원점수/기여·명시 필수/제외 조건은 보존한다. R05 저장/피드백·Backend·웹과 전체 R08,
실서비스 카탈로그/사용자 품질·최종 평가 완료를 주장하지 않는다. 업무DB·신규 원천 수집은 필요하지 않다.

기존 B1은 관련성 순위를 제공하며 같은 sku_group의 변형을 별도 후보로 포함할 수 있다. 이는 기존
B1의 결함이나 나쁜 성능 기준선이 아니다. 탐색 영역에서는 관련성만으로 정렬한 후보와 그룹/중복을
제한한 정책을 구분할 필요가 있어 새로운 명시 계약으로 구현했다.

구현 전2026-11-01 21:47:21.790325Z에8개 허구 상품·시연 가격·명시 그룹/프로필/필수 조건과
기대 불변식을 동결했다. spec SHA:
`2b30fba489c040e19a07ae5a484b1bbe657747106bfe71d52f1b391d5b5784cb`.
기존 B1을 실제 fit/rank한 top3은 `[1,2,3]`/명시2그룹이었다. 기대는 anchor1·그룹 중복 없음·
ID7제외/8비노출·0점 제외·원점수/기여 보존이며, 새 순위가 사람의 선호에 더 좋다는 라벨은 만들지 않았다.

## 대안과 구현

- 단순 그룹 중복 제거만으로도 같은 변형의 반복을 줄일 수 있지만 다른 그룹 간 특성 중복은 남는다.
  무작위 섞기는 관련성/재현성이 약하고 unknown을 새로움으로 쓰는0 cosine은 정보 부족을 우대한다.
- [원 MMR 논문](https://www.cs.cmu.edu/afs/cs/Web/People/jgc/publication/MMR_DiversityBased_Reranking_SIGIR_1998.pdf)의
  관련성과 선택 집합 중복도 분리를 참고했다. 기존 B1 관련성 상위100 안의 양수/floor 후보만 greedy
  선택하며 명시 그룹당 최대1개·관측 불가 쌍의 보수 벌점1을 추가했다. 초기 λ0.7과 floor0은 학습한
  최적값이 아니며 허용 λ0.5–1도 명시 정책이다.
- `FittedContentModel.fit/rank`를 그대로 재사용한다. 모델을 새로 구현하거나 두 번 fit하지 않는다.
  TF-IDF 알려진 원자 텍스트로 최대100×100 중복도를 계산한다. 상한 밖 후보를 찾아 보충하거나
  선택 수를 채우려고 hard/floor/group 제약을 완화하지 않는다.
- 기존 items의 score/reasons/contributions와 별도 selections의 MMR값·벌점·관측 similarity/basis를
  분리한다. unknown은 새로운 스타일/맛이 아니다. 풀 상한·전체 적격/실제 풀·floor 통과·선택 수와
  cold/floor 이유를 응답에 명시한다. 자세한 계약은 [EXPLORATION-API](../EXPLORATION-API.md)다.
- 기존512KiB/10초 수신·중복 JSON 고정 진단·원래 media별 문법 오류 우선순위·startup 무모델
  경계를 새 endpoint에도 적용했다. 이 receive deadline은 CPU fit 취소/성능 보장이 아니다.

## 실제 실행과 구분

같은 동결8상품을 own Uvicorn/OS 동적 loopback에서 두 API로 호출했다. 기존 B1 응답은 구현 전
결과와 전체가 같았고 `[1,2,3]`/2그룹, 탐색은 `[1,3,4]`/3그룹이었다. hard 통과6·floor 통과4·
선택3으로 원점수/기여를 보존했고 탐색 응답 두 번은 전체 동일했다. 소유 PID 종료를 확인했다.
이는 허구 입력의 정책 동작 차이이며 서비스 품질/전환/속도 개선이 아니다.

이 고정 조건에서는 anchor와 query 표현이 같고 λ0.5라 일부 MMR값이 동률이다. 추가 순서 변화가
MMR 자체의 효과인 것처럼 표현하지 않고 group 제한 효과로 기록한다. 별도 숫자 선호/학습 범위를
명시한 자체 회귀에서만 known text의 MMR 선택·λ1의 관련성 순서 보존을 확인한다. 그 보조 조건을
원래 동결 조건의 분모/성능으로 합산하지 않는다. 초기 테스트가 no Content-Type 오류를 json_invalid로
가정했으나 실제 기존 framework는 model_attributes_type이었다. 기존 content 응답과 정확히 대조하는
회귀로 고쳤고 제품의 오류 우선순위는 바꾸지 않았다.

신규 외부 원천 조회0·실서비스 카탈로그 fit0·새 업무 매핑0이다. 기존 별도 DEMO1상품 fit,
2제조사/11상품군5fit6transform의 낮은 지원과 사실 공유 한계,6상품군/11문맥/4정의·family unknown은
이번 허구 시연과 비합산으로 유지한다. 독립 선호 라벨이 없어 Recall/NDCG를 산출하지 않는다.

Python3.12.14 `./scripts/check.sh` 전체가 성공했다. Ruff/포맷·617개 pytest·기존 고정 시나리오·
새 sdist/wheel/runtime-only 격리 설치를 통과했다. checkout 밖 `python -I`의 실제 HTTP에서
health/B0/B1/exploration/OpenAPI·정책/입력 거절·원점수/그룹/상태 격리와 production10초 부분
본문408을 확인했다. 새 회귀28개와 관련 기존 content/JSON을 포함한100개 사전 검사를 통과했고
기존 TestClient deprecation 경고1개가 남았다. 테스트 수·CI 시간은 서비스 성능 수치가 아니다.
원본 허구 실행/모델 응답·동결 명세·proof/PID/로그는 ignored에만 보관한다.

## README와 후속

새 추천 기능의 필수/unknown/설명 경계는 구현했지만 현재 사례의 실제 원천 오류/HTTP 입력 의미
유실 수정보다 독립 채용 사례로 더 강하다는 근거는 부족하다. 기능 표에만 반영하고 기존 대표2/4와
순서를 보존한다. 실제 허용 다중 서비스 카탈로그·고정 관련성/사용자 없는 사실 평가·R05/Backend/웹
연결 후 다시 비교한다. top100 밖 누락·그룹 메타 오류·보수 unknown에 따른 탐색 기회 축소와
request-local fit/통신 비용은 남은 한계이며 측정하지 않은 성능 수치를 만들지 않는다.
