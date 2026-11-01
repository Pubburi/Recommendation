# 명시적 취향 확장 후보 API — R08 기술 증분

`POST /v1/recommendations/exploration`은 기존 B1의 관련성 점수를 재사용해 **별도 탐색 영역**에 쓸
후보를 고른다. 기존 `/baseline`·`/content` 요청/응답·순위·점수·기여는 변경하지 않는다. 전체 R08,
Backend/웹 연결·피드백 저장/반영·실제 서비스 카탈로그 품질은 아직 완료가 아니다.

## 요청

[B1 content 요청](CONTENT-API.md)의 명시 catalog/profile/constraints/limit을 그대로 받고 선택적인
`policy`를 추가한다. catalog 최대1000·limit 정수1–100·엄격한 타입/필드·필수/제외 조건을 유지한다.

```json
{
  "catalog": [],
  "profile": {},
  "constraints": {},
  "limit": 12,
  "policy": {"relevance_weight": 0.7, "min_relevance_score": 0.0}
}
```

relevance_weight는 유한 숫자0.5–1, min_relevance_score는 유한 숫자0–1이다. 기본값은 초기 정책이며
사용자에게 최적인 학습/튜닝 결과가 아니다. 문자열 숫자·boolean·NaN·추가 필드는422로 거절한다.
`sku_group`은 제공자가 검수한 변형 그룹이다. 이름/브랜드/원천 QID로 자동 추정하지 않는다.

입력 권리·상품 정체성·현재 업무 ID와 필드 검수는 기존 B1처럼 호출자 책임이다. 이 API는 동의
flag로 권리를 대신 승인하거나 legacy80개를 학습 자료로 자동 허용하지 않는다. 요청 전체 catalog에
지역적으로 fit하므로 known-catalog 표현이며 사용자 선호 학습/신규 상품 일반화 평가와 다르다.

## 선택 정책

1. 기존 `FittedContentModel.fit/rank`로 필수 조건을 통과한 관련성 상위100개만 받는다. 요청 limit과
   달리 이 후보 풀 상한은 고정이다. 같은 group 변형이 풀을 채워도101번째 후보를 찾아 보충하지 않는다.
2. 양수이면서 min_relevance_score 이상인 후보만 남긴다. 무관한0점·최소값 미달·제외/조건 탈락을
   다양성을 이유로 복구하지 않는다. 빈/OOV/무매칭 취향의 기존 fallback에서는 탐색 items를 반환하지 않는다.
3. 첫 항목은 관련성 최고 후보다. 이후에는 이미 선택한 후보와의 텍스트 중복을 벌점으로 삼는다.
   선택값=`λ × B1점수 − (1−λ) × 최대 텍스트 cosine`이다. 동점은 B1점수 내림차순·ID 오름차순이다.
4. cosine은 동일한 fit 어휘/IDF로 변환한 알려진 category/taste/aroma 원자 토큰만 사용한다.
   수치 unknown/빈 text를0 similarity의 '새로움'으로 보상하지 않는다. 한쪽이라도 zero vector인
   비교는 관측 similarity를 null로 두고 **보수적인 벌점 입력1**로 처리한다. 숫자 취향만 지원될 때
   선택은 가능하지만 새로운 주종/스타일을 확인했다는 뜻이 아니다.
5. 각 명시 sku_group에서 최대1개만 선택한다. 부족하면 더 짧게 반환하며 관련성/필수 조건·그룹을
   완화하거나 중복으로 채우지 않는다. 선택순이 B1점수 내림차순과 다를 수 있다.

이 정책은 [Carbonell·Goldstein의 MMR 원논문](https://www.cs.cmu.edu/afs/cs/Web/People/jgc/publication/MMR_DiversityBased_Reranking_SIGIR_1998.pdf)의
관련성/중복도 분리에서 출발한 제한적 변형이다. 추가한 relevance floor·그룹 제한·unknown 정책은
프로젝트의 명시 규칙이다. 문서 검색 논문의 실험 결과를 주류 추천의 품질 근거로 사용하지 않는다.
MMR 선택은 전역 최적 다양성이나 실제 취향 확장을 보증하지 않는다.

## 응답과 설명

기존 B1 응답 필드에 fit_scope/representation_fitted와 다음 metadata를 더한다.

| 필드 | 의미 |
|---|---|
| algorithm / reranking_algorithm | `b1-tfidf-minmax-v1` 기반 / `r08-text-mmr-group-v1` 선택 정책 |
| eligible_count | 기존 hard 조건을 통과한 전체 수. 탐색에 사용할 수 있다는 뜻은 아님 |
| candidate_pool_limit/size, pool_truncated | 관련성 상위100 상한·실제 풀 수·상한 밖 후보 존재 여부 |
| relevance_pool_size | 풀 안에서 양수/floor를 통과한 수, 그룹 선택 전 |
| selected_count/selected_group_count | 최종 항목/명시 그룹 수 |
| exploration_reason | selected / baseline_fallback / below_relevance_floor |
| selections | items와 같은 순서의 product_id·sku_group·선택값·벌점 입력·관측 cosine·근거 종류 |

**items의 score/reasons/contributions는 원래 B1 값 그대로다.** 점수/기여의 합은 MMR 선택값이 아니다.
selections의 basis는 highest_relevance_anchor, observed_text 또는 unknown_conservative다.
관측 cosine이 null인 경우를 새로운 스타일/다른 맛이라고 설명하지 않는다. B1 fallback_reason은
그대로 보존하고 floor 미달은 별도 exploration_reason으로 구분한다. 후보가 없어도 fit을 실행했는지와
사용 가능한 표현이 있는지를 혼동하지 않는다. 빈 catalog는 fingerprint null/representation_fitted false다.

## 실행·보안·검증 한계

다른 추천 POST와 같은512KiB 누적 본문/전체10초 수신 기한·중복 JSON 키 고정 진단·원래 문법 오류
우선순위를 적용한다. CPU fit을10초에 취소한다는 뜻은 아니다. 시작/스키마/health/빈 요청은 모델
런타임을 로딩하지 않는다. DB·외부 API·모델 파일·입력/개인 상태 저장·요청 간 cache를 사용하지 않는다.

현재 검증은 직접 작성한 허구 상품의 기능/제약·같은 그룹·unknown·실제 fit/HTTP와 설치 패키지
경계다. 기존 실제1업무 DEMO·11상품군·11문맥 관측의 분모를 합치거나 새 서비스 fit/품질 성과로
쓰지 않는다. [사전 명세·실행 결과](plans/2026-11-02-exploration-reranking.md)를 따른다.
