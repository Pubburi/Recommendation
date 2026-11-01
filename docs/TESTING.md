# 추천 서버 검증

Python 3.12와 CI에 고정한 uv로 `./scripts/check.sh`를 실행한다. 저장소 비밀정보/생성물 검사,
잠금 의존성 설치, Ruff 정적 검사/포맷, 서비스 경계 테스트, 배포 산출물 검증을 같은 순서로 수행한다.
PR·main push·수동 실행의 필수 `recommendation-ci`가 이 검증을 실행한다.

## 배포 산출물 검증

`uv run --locked python scripts/smoke_distribution.py`는 아래를 확인한다.

1. 빈 임시 디렉터리에 sdist와 wheel을 새로 빌드한다. 기존 `dist/`에 남은 오래된 wheel을 선택하지 않는다.
2. `uv export --locked --no-dev --no-default-groups --no-emit-project --no-sources`로 runtime 요구사항을 추출한다.
3. 임시 venv에 해시 검증한 잠금 runtime 의존성만 설치하고, 방금 빌드한 wheel을 `--no-deps`로 설치한다.
4. `uv pip check`로 배포 메타데이터의 의존성 정합성을 확인한다.
5. checkout 밖에서 `python -I`로 import 경로가 임시 환경에 있는지 확인하고 실제 Uvicorn을 실행한다.
6. OS가 할당한 loopback 포트에서 `/health`·`/openapi.json`과 B0 추천 POST를 검증한다.
   조건을 요구하는 미확인 가격·판매 불가 후보가 제외되고, 중복 ID 요청은 422인지 확인한다.
   B1 content POST도 실제 fit/기여·조건·OOV/빈/무정보·요청 격리·422/413과 production10초의
   실제 부분 HTTP 본문408을 확인한다. 시간 제한을 줄인 서버 설정으로 대체하지 않는다.
7. 새 wheel의 runtime-only `python -I`로 `content_experiment`를 실제 실행한다. 직접 작성한
   fixture의 vocabulary/IDF·수치 fit과 명시 상품군 분리·필수 조건 결과를 확인한다. 원문/모델을
   Git이나 artifact에 업로드하지 않으며 실제 상품 품질 평가로 표현하지 않는다.
8. `legacy_seed_audit`도 runtime-only 실제 CLI로 작은 자체 SQL literal/바이트 시그니처를
   감사한다. 실제80행/이미지는 CI가 읽지 않으며 결과가 자동 학습 승격을 만들지 않는지 확인한다.
9. `wikidata_collect`는 자체 item payload의 성공 offline 재생·maxlag/깊은JSON 실패를 새 wheel의 실제
   CLI로 확인한다. CI는 원천 네트워크를 호출하지 않으며 재생을 신규 수집/카탈로그 품질로 쓰지 않는다.
10. `source_family_experiment`는 자체3항목을 실제 수집 CLI로 offline 재생한 영수증/검수/hash와
    연결해 새 wheel의 runtime-only `python -I`에서 실제2fit/1transform을 실행한다. 학습 어휘·
    OOV·용량 미지원·fixture 표시를 확인하며 원문·학습 파라미터는 artifact에 포함하지 않는다.
11. 같은 자체 snapshot/receipt로 `package_identity_audit`를 runtime-only `python -I`에서 실제
    실행한다. 문자열 GTIN 체크·포장 필드 부족·완성 receipt와 매핑/fit승격0을 확인한다.
    외부 GTIN 할당 조회나 실제 주류 카탈로그를 CI에서 사용하지 않는다.
12. 별도 자체 container payload의 offline accepted receipt/명세를 `source_catalog`의 실제
    runtime-only CLI에 전달한다. source-only 필드/provenance·원래 혼합 분류/hold·명시 scope와
    완성 receipt, 업무 ID/매핑/wire export/서비스 fit 비승격을 확인한다. 외부 검수 URL은 fetch하지 않는다.

HTTP 과정에 DB·AWS·모델·외부 AI API 환경변수를 전달하지 않는다. 8000 포트를 점유하지 않고
본인 서버 프로세스와 임시 환경만 정리한다. 현재 검증 대상은 Linux/macOS이며 CI는 Ubuntu다.
격리 import/OpenAPI 검사는 기존10초 제한을 유지하며 NumPy/sklearn 미로드를 확인한다. 첫
nonempty B1 요청의 지연 로딩은 별도의 HTTP 클라이언트30초 한계에서 검사하고 기존 health/B0의
1초 클라이언트 한계는 유지한다. 이것은 서비스 지연 개선이나 CPU 작업 취소의 보장이 아니다.
성공한 새 배포 파일은 로컬 `dist/`에 보존한다. 생성물·runtime 요구사항·서버 로그는 Git에 추가하지 않는다.
CI는 성공/실패와 무관하게 JUnit과 단계/결과만 담은 smoke JSON을 artifact로 7일 보관한다.
원문 서버 로그·실제 환경변수·venv·데이터는 artifact에 포함하지 않는다. 보고서는 로컬 `reports/`에 생성되며 무시된다.

이 검증은 패키징 누락·checkout의 소스/개발 의존성에 대한 숨은 의존·실제 HTTP 계약 회귀를
확인한다. B0 계약의 기능 검증은 학습 모델·실제 사용자 선호 품질·Backend 통합 검증을 뜻하지 않는다.

## B0 추천 계약의 회귀 검증

`tests/test_baseline.py`는 직접 작성한 가상 입력으로 판매 상태·주종·가격/도수 범위·제외 조건,
unknown과 0의 구분, 후보 부족 시 조건 유지, 필터 뒤 limit, 입력 순열과 무관한 결과를 확인한다.
잘못된 타입·범위/상한·중복 ID·미지정 필드, 512 KiB 원문/ASGI 누적 크기 제한과 비유한 수치
입력의 JSON 오류 응답도 검증한다. fixture 값은 실제 상품 사실·사용자 행동·평가 정답이 아니다.
기본 기준선은 학습 전 비교 대상으로 구현한 신규 기능이며 과거 모델의 장애/성능 개선으로 쓰지 않는다.

## 오프라인 원천 감사

`tests/test_catalog_audit.py`는 직접 작성한 가상 entity로 권리 보류를 입력 읽기 전에 확인하는지,
단위 변환·범위/문맥/다중 값의 unknown·deprecated·라벨 누락·브랜드/SKU 분리·원문 해시와
검수 mapping·명시 Backend ID/그룹/시연 가용성·가격·B0 계약·출력 덮어쓰기 차단을 검증한다.
실제 CC0 소량 표본 감사와 이 회귀 fixture는 구분하며 CI가 원천을 다운로드하지 않는다.
격리 wheel 검증은 checkout 밖에서 CLI `--help`도 실행해 runtime 의존성/패키징을 확인한다.
ko/en 우선순위·mul-only 기본 라벨·원천 label_language·실제 unknown·설명/별칭 비추론·라벨 상한과
동일 revision이라도 새 raw 해시에 이전 검수가 재사용되지 않는 경계도 검증한다. 새 wheel의 실제
수집 CLI는 직접 작성한 mul-only payload를 offline 재생해 라벨과 원천 언어가 보존되는지 확인한다.

`tests/test_legacy_seed_audit.py`는 작은 직접 작성 SQL·로컬 바이트 fixture로 활성 INSERT/주석·
quoted text·컬럼/리터럴 상한·지원 불가/변경문 거절, 사용자/암호 행 비노출, Decimal 타입/정확값·
unknown/실제0·언더플로, 웹 매핑·경로/시그니처/해시·중복·symlink/파일 크기와 새 출력 보존을 검증한다.
DB/SQL 실행·네트워크·실제 이미지 변환·학습은 수행하지 않는다. 실제80행 관측 집계와 단위 테스트의
고정 정답을 결합하지 않으며 [감사 범위·실제 결과](LEGACY-SEED-AUDIT.md)를 별도로 관리한다.

`tests/test_wikidata_collect.py`는 고정GET/요청 상한·UA/maxlag/timeout·redirect·잘못된 HTTP/크기·
JSON 중복/비유한 값/재귀 한계·APIerror/warning·누락/추가/redirect item·revision·실패 receipt·출력 보존과
offline 모드/권리 승인 경계를 검증한다. 실패한 새 snapshot이 이전 정상본이나 empty 성공을 만들지
않는지 확인한다. 실제 원천 maxlag와 기존4항목 재생 결과는 [수집 기록](WIKIDATA-COLLECTION.md)으로
별도 보존하며 실제 상품 부재·카탈로그 학습 완료로 해석하지 않는다.

실제 `HTTPResponse` decoder에 종료 chunk가 누락된 자체 wire를 제공해 `IncompleteRead`를
재현하고 fetch·별도 프로세스의 실제 CLI parser/main이 고정 protocol 진단·exit2·완성 실패
receipt를 남기며 원문/정제 파일을 생성하지 않는지 확인한다. 네트워크·외부 원천 요청은 없다.
선언 길이보다 짧지만 완결된 JSON인 자체 응답도 같은 실패 경계를 검증한다. 정확한 길이·길이 없는
EOF·정상 chunked의 성공을 보존하고, 잘못된/중복 Content-Length·길이와 전송 인코딩의 충돌·
네이티브 decoder가 처리하지 않는 인코딩·상한 초과 선언을 본문 읽기 전에 거절하는지 확인한다.

`tests/test_package_identity_audit.py`는 작은 자체 GTIN/원천 shape로8/12/13/14자리와 검증 숫자·
ASCII/선행0/all-zero, qualifier/deprecated/다중/공유 식별자·브랜드/container 혼합을 확인한다.
한쪽만 qualifier가 있는 활성 GTIN도 양쪽 공유키 보류가 되어 수동 후보로 우회하지 못하는지,
deprecated 식별자를 활성 충돌로 잘못 집계하지 않는지도 확인한다.
수량 statement의 rank/snak/type·문맥과 기존 단위/범위/다중 값 처리에서 unsupported 값이
포장 근거가 되지 않는지 검증한다. 실제 CLI의 새 ignored 출력/완성 receipt·기존 결과 보존·
snapshot/receipt/검수 해시와 revision 결속·고정 진단과 자동 매핑/fit 비승격도 확인한다.
자체 checksum 통과와 실제 원천4항목의 [별도 관측](PACKAGE-IDENTITY-AUDIT.md)은 구분한다.

## 독립 고정 시나리오

`tests/test_source_catalog.py`는 허구 사실과 고정 수동 명세로 원천/provenance·한정 mixed scope·
미확인 값·모순/변경 입력·ID/검수 링크·UTC를 검증한다. 미선택 item의 qualified GTIN 충돌도
선택한 item의 보류를 우회하지 못한다. 실제 subprocess CLI의 새 ignored 출력/기존 결과 보존과
부분 쓰기 실패의 incomplete receipt·원문/개인 경로 비노출을 확인한다. 이것은 외부 페이지
권리/진실성 인증이나 서비스 상품 매핑·추천 학습/관련성 검증이 아니다.

단위 테스트 뒤 `scripts/evaluate_baseline.py`가 버전 고정 fixture를 ASGI 앱으로 실행하고,
`scenario_evaluation`이 생산용 점수/필터 helper와 분리해 결과를 검사한다. `tests/test_scenario_evaluation.py`는
명세 모순·해시/알고리즘·케이스 누락/중복·변조된 결과·제약/이유/순서·CLI 보호와 미래 모델의
제약 전용 정책을 검증한다. 기대값을 실행 결과로 만들지 않으며 Recall/NDCG는 미산출이다.

CI는 `reports/baseline-scenarios.json` 요약만 업로드하고 `baseline-responses.json`은 보관하지 않는다.
새 wheel에서는 runtime-only `scenario_evaluation --help`를 실행한다. 명세/정책과 한계는
[EVALUATION.md](EVALUATION.md)를 따른다. 이 ASGI runner는 실제 서버 간 통합 E2E가 아니다.

## B1 오프라인 fit·누수 경계

`tests/test_content_model.py`는 vocabulary/수동 계산 IDF·관측 수치 범위의 실제 fit,
한국어 한 글자/띄어쓰기 태그·맛/향 namespace, fit 미호출 transform, unknown과 실제0·분모/기여,
상수/결측 열 비활성화·빈/OOV/zero-vector fallback, 필수/제외·동점/순열·선택 상품 제외,
엄격 타입/상한과 상품군 교차/미지정·수동 기대 사실 모순·CLI 출력 보존을 검증한다.

필수 CI와 `check.sh`의 `scripts/evaluate_content.py`는 허구11상품을 학습4/3그룹·변환7/6그룹으로
나누어 8개 계약 시나리오를 실제 실행한다. 학습에 없는 태그·수치가 vocabulary/범위에 유입되지
않는지 확인한다. `reports/content-fit-summary.json`만 7일 보관하고 원문·응답·어휘/IDF는 제외한다.
고정 fixture의 B0/B1 순서 비교는 품질 개선이나 최종 holdout이 아니다. 독립 관련성 라벨이 없어
Recall/NDCG는 미산출이며 사용자 선호 학습·실서비스 카탈로그 fit·Backend B1 통합은 남아 있다.
[모듈·수식·실행 경계](CONTENT-MODEL.md)를 따른다.

## B1 요청 카탈로그 HTTP 계약

`tests/test_content_api.py`는 허구 입력으로 실제 엔진의 HTTP 연결을 검증한다. 필수/제외·unknown/
실제0·기여 합/이유·soft/hard 구분·빈/OOV/공유 특성 없음·빈/무정보 catalog의 usable representation,
엄격 타입/상한·422원문 비노출·512KiB를 확인한다. 단독/순열·동시 요청에서 vocabulary/scaler/
fingerprint와 결과가 다른 요청의 상태에 영향받지 않는지 검증하고 시작/health/B0 fit도 금지한다.
새 프로세스의 main/OpenAPI에서 수치 라이브러리 미로드도 확인한다. 경량 계약을 분리하고 기존
offline import 경로를 재노출해 서버 스키마 초기화가 학습 라이브러리 로딩을 요구하지 않게 한다.
ASGI 무응답/드립의 절대 deadline·누적 chunk/끊긴 연결은 두 POST에 적용하며 parser/fit 진입 전에
고정408/413 또는 연결 종료로 처리한다. 요청 전달 fixture를 실제 서비스 SKU 학습/품질로 쓰지 않는다.

## source 상품군의 별도 표현 실험

`tests/test_source_family_experiment.py`는 수동 DF-IDF·관측 수치 범위, held-out 사실 변화 시
학습 파라미터/fingerprint 불변, 그룹 교차/미지정·브랜드/SKU 비승격·사실 모순과 unknown/실제0·
상수/빈 어휘·OOV를 검증한다. 실제 collector receipt를 써서 파일/검증 모델 해시를 구분하고
권리·변경된 hash·API 오류/실패 영수증·모드/revision을 확인한다. 별도 프로세스 CLI는 비공개
새 출력·고정 진단·원자 게시·기존/경쟁 파일 보존도 확인한다. 이 직접 작성 회귀와
[실제 CC0 상품군 fit 관측](measurements/2026-11-01-source-family-fit.md)은 별개다. 추천 순위/
관련성·서비스 SKU·사람의 선호를 이 검사로 검증했다고 주장하지 않는다.

근거: [uv export/build](https://docs.astral.sh/uv/reference/cli/),
[Python isolated mode](https://docs.python.org/3.12/using/cmdline.html#cmdoption-I).
