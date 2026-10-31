# 고정 추천 시나리오와 독립 검사기

DAT03의 첫 증가분으로 UI·사용자·행동 로그 없이 실행하는 **계약 회귀 명세**를 제공한다.
`evaluation/baseline-contract-v1.json`의 8상품은 직접 작성한 허구 입력이다. 가격·도수는 이
명세 안의 조건 사실이며 실제 주류 관측값·사람의 취향·관련성 정답이 아니다.

## 정답과 실행 코드의 경계

- 명세에는 카탈로그 버전·알고리즘·각 시나리오의 입력 후보/조건/limit·수동으로 고정한 통과
  ID/반환 ID·선정 사실 설명이 있다. 실행 결과로 이 기대값을 생성하거나 갱신하지 않는다.
- 검사기는 추천 엔진·생산용 필터/이유 helper를 호출하지 않는다. DTO의 타입/범위 스키마만
  공유하고, 별도 조건 위반 검사와 명세의 선언값으로 결과를 확인한다. 따라서 스키마까지
  완전히 독립된 구현이라고 주장하지 않는다.
- 모순된 명세도 거절한다. 중복/미지정 후보·기대 ID·사실과 맞지 않는 통과 목록·B0의
  ID순/limit 기대값을 확인한다. 명세 변경 시 사실 근거를 재검토하고 버전을 갱신한다.
- 응답 묶음은 **명세 원문 SHA-256과 알고리즘**에 묶인다. 이는 어떤 명세와 비교했는지
  확인하는 무결성 근거이며 사실의 정확성·평가자 독립성을 자동 보증하지 않는다.

## 현재 고정 시나리오

| 시나리오 | 확인할 사실·동작 |
|---|---|
| cold-start-order | 취향/로그 없이 판매 가능한 후보를 ID순으로 정렬하고 limit 적용 |
| hard-constraint-intersection | 주종·가격·도수·관심 없음의 교집합, unknown과 판매 불가 제외 |
| inclusive-bounds-before-limit | 양 끝 포함·필터 뒤 limit, 통과 후보 수와 실제 반환 수 구분 |
| known-zero-not-unknown | 0원/0% 상한이 실제 조건이며 미확인을 0으로 만들지 않음 |
| unrequested-unknown-allowed | 요청하지 않은 특성 누락은 임의 제외/이유 생성의 근거가 아님 |
| no-matching-category | 맞는 주종이 없으면 조건 완화 없이 빈 결과 |
| all-explicitly-excluded | 제외된 상품을 결과를 채우기 위해 다시 노출하지 않음 |
| empty-catalog | 입력이 비어 있으면 0개·명시적 후보 없음 사유 |

각 결과에서 상태/응답 스키마·입력에 있는 상품인지·중복·판매/필수/제외·반환 상한·이유 코드·
통과 후보 수·빈 결과 사유를 검사한다. 누락/중복 시나리오나 무관한 성공 응답으로 전체 통과를
대체할 수 없다. B0에서는 선언된 반환 목록과 순서도 정확히 비교한다.

## B0 순서와 미래 모델의 품질을 구분

`ordering_policy=b0_id_ascending`은 현재 B0 wire 계약과 결정적 ID순을 검증한다.
이 순서를 B1 콘텐츠 관련성 정답으로 재사용하지 않는다.

향후 모델의 별도 응답 기록은 `constraints_only` 정책으로 최소 후보 envelope를 확인할 수
있다. 이때 알고리즘·상품 ID/이유·eligible_count/fallback_reason의 공통 의미를 맞춰야 하며,
원한다면 `expected_item_count`만 명시한다. `expected_item_ids` 순위 정답을 넣는 것은 거절한다.
ID순과 모델 점수·추가 설명 필드는 평가하지 않고, 중복/제약·활성 조건에 대한 필수 이유 코드만
확인한다. 보고서에 `minimal_candidate_envelope_only`와 검사 범위를 명시한다. **이 모드의
통과는 B1 wire 계약·점수·설명의 충실성·추천 관련성 통과를 뜻하지 않는다.** B1 모델/API는 아직 없다.

두 정책 모두 현재 데이터 성격은 `authored_contract_fixture`다. 독립적인 관련성 라벨이 없으므로
Recall/NDCG는 산출하지 않고 보고서에 미산출 사유를 남긴다. 학습/검증/최종 평가 분리·최종
holdout·카탈로그 품질·사용자 만족도·CTR/구매 전환·응답 성능은 이 회귀 명세의 결과가 아니다.

## 실행과 보고서

```bash
uv run --locked python scripts/evaluate_baseline.py
```

현재 runner는 B0 명세만 받고 FastAPI TestClient를 통해 앱을 호출한다. 실제 외부 네트워크나
Backend/DB 통합 E2E가 아니다. 원본 응답은 ignored `reports/baseline-responses.json`에,
원문 입력을 포함하지 않는 집계/케이스 판정은 `reports/baseline-scenarios.json`에 기록한다.
기본 runner는 자신이 소유한 이 두 생성물을 재생성한다. API·health·데이터 수집 동작은 바꾸지 않는다.

기록한 응답을 독립 CLI로 다시 검사할 수 있다.

```bash
uv run --locked python -m pubburi_recommendation.scenario_evaluation \
  --suite evaluation/baseline-contract-v1.json \
  --responses reports/baseline-responses.json \
  --output .pubburi/scenario-check/new-report.json
```

CLI 출력은 `.pubburi` 또는 `reports` 아래에만 두고 기존 보고서를 덮어쓰지 않는다.
입력 파일은 10 MiB 이내·명세/응답은 각 1000케이스 이내로 제한한다. CLI 종료 코드는
0=정한 범위 통과, 1=응답 위반 발견, 2=명세/해시/알고리즘/입출력 문제다. 오류에 원문
카탈로그·응답 본문·개인 경로를 노출하지 않는다.

보고서는 명세/응답 해시·카탈로그 버전·알고리즘·검사 정책·전체/통과/실패 케이스·위반 코드와
미산출 지표/한계를 포함한다. `issue_case_counts`의 분모는 케이스이며 상품별 오류율이 아니다.
무관한 응답은 전역 위반으로 전체를 실패시키므로 개별 케이스가 통과했더라도 전체 상태를 확인한다.

필수 `recommendation-ci`와 `./scripts/check.sh`에서 단위 검증 뒤 고정 시나리오를 실행한다.
CI는 요약 보고서만 7일 보관하며 원본 응답·카탈로그는 올리지 않는다. 검사기 자체는 오류 응답
주입으로 확인하고, 새 wheel의 runtime-only 환경에서도 CLI 진입점을 점검한다. 검사기 통과나
주입 오류 탐지 개수를 서비스 품질·실제 오류 감소·성능 개선 수치로 쓰지 않는다.

다음 단계는 허용된 실제 SKU 카탈로그·독립 관련성 명세·B1 fit과 비교, 상품군 분리와 누수 확인,
업무 저장/권한·피드백·화면·장애 통합 검증이다. DAT03 전체 완료와 구분한다.
