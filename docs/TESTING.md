# 추천 서버 검증

Python3.12와 고정 uv로 `./scripts/check.sh`를 실행한다. PR·main push·수동 실행의 필수
`recommendation-ci`도 같은 검사를 수행한다. 실행 순서/배포 검사의 정본은
[check.sh](../scripts/check.sh), [CI](../.github/workflows/ci.yml),
[smoke_distribution.py](../scripts/smoke_distribution.py)다.

## 실행과 결과

```bash
./scripts/check.sh
# 수정 영역을 먼저 확인할 때
uv run --locked pytest tests/test_source_family_experiment.py tests/test_source_family_evaluation.py
```

전체 검사는 저장소 비밀정보/생성물 → `uv sync --locked` → Ruff/format → pytest →
동결 B0/B1 시나리오 → 새 sdist/wheel 검증 순서다. 테스트 수·실패/수정 이력과 현재 head의
실행 결과는 PR/CI에 남긴다. 회차별 계획·측정 문서나 같은 assertion 설명을 추가하지 않는다.

CI는 pytest.xml·baseline-scenarios.json·content-fit-summary.json·distribution-smoke.json만
7일 보관한다. 원문/업무 응답·전체 순위·어휘/IDF·모델·실사용 로그/비밀정보를 업로드하지 않는다.

## 유지하는 경계

| 영역 | 핵심 검사·소스 |
|---|---|
| startup/B0 | [health](../tests/test_health.py)·[baseline](../tests/test_baseline.py): DB/모델/네트워크 없는 초기화, 필수/제외·unknown·실제0·결정적 기본순 |
| HTTP 입력 | [request JSON](../tests/test_request_json.py):512KiB 누적 본문·10초 수신기한, 중복 decoded key 거절과 malformed 우선순위 |
| B1 모델/누수 | [content model](../tests/test_content_model.py): atomic 태그/IDF·관측 수치·unknown mask, train-only fit/transform, 그룹 분리·상수/OOV/empty fallback·실기여 |
| 기존5B1 제공자 | content_api/exploration/similar/context/feedback의 전용 tests:1fit·원점수/이유·hard/그룹/negative 제외·기준/선택 metadata·빈/미평가 상태 |
| 설명/저장 취향 | [설명](../tests/test_content_explanations.py)·[취향](../tests/test_preference_input.py):기존 wire 보존, actual/target/단위·winning ID, soft/hard·null/[]/0·raw Decimal·명시 충돌 |
| R06 검색문구 | [search phrases](../tests/test_search_phrases.py): opt-in·exact literal/UTF16·정밀도, typed query·분기/생략·진단, soft 비승격·무모델 |
| 원천/수집 | [catalog audit](../tests/test_catalog_audit.py)·[Wikidata](../tests/test_wikidata_collect.py):accepted receipt·exact ID/revision/hash, maxlag/HTTP 오류·부분 응답·고정 URI/metadata·기본 라벨 |
| 포장/정체성 | package_identity/source_relation_integrity/gtin_metadata/volume_context 전용 tests:property/datatype·단위·rank/qualifier·공유 ID hold·문맥별 관측, 미확인 사실 비승격 |
| legacy seed | [legacy audit](../tests/test_legacy_seed_audit.py):SQL literal/읽기 예산·이미지 서명 검사, 실행/비밀행/권리 추정 없는 격리 |
| 정제/업무 export | source_catalog/family_browse_catalog/business_export tests:source 권위·정확 사실/whole response hash·명시 ID/그룹·origin/freshness·unknown·무매핑/혼합 거절 |
| 소비 bundle | [checked export](../tests/test_checked_export.py)·[bundle](../tests/test_backend_catalog_bundle.py):완료4파일 exactbytes·원authority 재검증·fresh/replay 분리·원capture 만료·pinning·실패 미발행·기존출력 보존 |
| 독립 평가 | [scenario](../tests/test_scenario_evaluation.py)·[reviewed fit](../tests/test_reviewed_catalog_fit.py):fit 전 동결 사실·후보/제약/반환/이유, 생산 scorer/필터로 정답 생성 금지 |
| 원천 상품군 | [family experiment](../tests/test_source_family_experiment.py)·[cohort](../tests/test_source_family_cohort.py)·[fact evaluation](../tests/test_source_family_evaluation.py):각 snapshot 권위·train-only 어휘/스케일·미관측 제조사/그룹 분리·전체 순위/양성/생략 분모 |

## 배포 패키지

smoke_distribution은 임시 디렉터리에 새 sdist/wheel을 빌드하고 고정 runtime 요구사항을
해시 검증해 새 venv에 설치한다. checkout 밖 `python -I`의 import 위치와 의존성을 확인한 뒤
OS가 할당한 loopback 포트에서 health/OpenAPI·기존7POST의 실제 HTTP를 검증한다.
512KiB/422·production10초 부분 본문408과 기본 wire·명시 사실/제약/이유/fallback을 포함한다.
수신기한이 CPU fit을 취소한다는 의미는 아니다.

설치된 wheel의 authored source/정제·mapping/export/fit·checked5B1 인수/bundle CLI도 실제
실행한다. 이 검사는 원천을 네트워크 수집하지 않으며 원본 업무 DB를 읽지 않는다. 런타임 모델
다운로드·startup fit을 추가하지 않는다. 미채택 SVD 비교는 현재 패키지/검사 대상에서 제외했고
당시 [실측/고정 코드](measurements/2026-11-03-source-representation-comparison.md)를 보존한다.

검증 fixture·DEMO·같은 조건의 재현을 실사용자 관련성/서비스 카탈로그 품질로 세지 않는다.
[평가 계약](EVALUATION.md)과 [데이터·모델 정본](DATA-AND-MODEL-PLAN.md)의 권리·unknown·
누수/고정 명세·지표 미산출 경계를 유지한다. 특정 결함의 전후 원값은 해당 강한 측정 보고서에,
원시 snapshot/모델/로그는 ignored에 보존한다.
