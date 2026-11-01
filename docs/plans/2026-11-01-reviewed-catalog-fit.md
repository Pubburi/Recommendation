# AI03/DAT02–04 — 실제 검수 카탈로그 fit 증가분

- 기준 main `7cc9cea`, `codex/reviewed-catalog-fit`. 자기 레포만 작성하고 root는 전용 업무
  publish/snapshot·통합 환경·기획/PR/최신 리뷰/CI/병합/main CI·브랜치/lease를 소유한다.
- 새 gate 반복으로 끝내지 않고 기존 원천/업무 검수·B0/B1 엔진을 재사용하는 실행 workflow를
  구현했다. 실제 CC0 포장 후보1을 root가 별도 전용 업무 DEMO API에 등록/읽었다.
  실제 source 사실과 허구 fixture를 origin으로 구분하고 명시 DEMO가격/주종·placeholder를
  source 도수/용량·이름과 분리했다. 기존80/사용자DB는 quarantine/무변경이다.
- root의 fresh snapshot을5분 내 명시 매핑하고 실제 B1 fit/B0 비교를 실행했다. fit 전에
  고정한 source key의 facts와9개 시나리오/원hash를 유지한다. 범위/가격/주종·제외·unknown/
  OOV/상수/콜드스타트를 독립 요구사항 검사기로 확인하고 결과/기여를 검사했다.
- 실제1product/1group·TF-IDF 업무주종1token/IDF1, 원천 도수5/volume500 관측은 각1개라
  거리 특성은 비활성이다. unknown 맛/향은 유지하고9개 계약 통과를 순위 품질·사용자 만족도나
  일반화/최종 평가로 바꾸지 않는다. 별도 실행의 같은 fit 요약/어휘/IDF·fingerprint/케이스를
  확인하며 실행 시각은 구분한다. 원본/명세·모델 파라미터/응답은 ignored에만 둔다.
- 공식 CC0·bottle Q80228·WDQS 조건을 확인하고 명시 can/bottle/volume/ABV LIMIT10 GET을
  한 번 수행했으나 기존1ID만 있어 신규0이다. 원천 전체의 부족이 아니라 해당 조건의 표본 한계다.
  반복 수집/즉시 재시도·aT 거절 우회·외부 폼/문의·키/유료/AWS·이미지 수집은 하지 않았다.
- CLI는 기존 권리/원문/revision·업무 snapshot/매핑을 다시 검증한 뒤 frozen 사실/전체 key와
  모순이 없는 경우만 기존 모델을 fit한다. B0/B1 후보/중복/조건/이유/개수·score기여/기반 특성을
  검사하고 `completed`/`passed`·실행/동결 시각·원본 hash를 구분해 기록한다. 시작/health/API에
  모델 준비나 저장을 추가하지 않고 외부 사용자/로그를 선행 대기로 두지 않는다.
- README2/4/순서를 보존한다. 실제 데이터-업무 ID-학습 실행의 근거는 늘었지만 단일상수
  카탈로그의 결과이고 독립 순위/서비스 영향·다중 그룹 평가가 없어 기존 원천/데이터 경계
  소재보다 강한 독립 모델 사례로 조기에 승격하지 않는다. [실측 조건](../measurements/2026-11-01-reviewed-catalog-fit.md)을
  보존하고 다음에는 제품 다양성과 실제 다중 그룹/관련성 평가를 우선한다.

최종 회귀/배포 검증·미완료/PR 상태는 아래에 기록한다. 전체 AI03·서비스 카탈로그 품질/Backend
B1 자동 연동·배포·20개 기능 완료와 이번 known-catalog fit1개 증가분을 구분한다.

- 최종 로컬 검증: Python3.12.14 `./scripts/check.sh`에서 저장소 안전 검사·locked 설치·
  Ruff/format·pytest453개·기존 authored B0/B1 계약·새 sdist/wheel을 통과했다. 개발 의존성
  없는 별도 설치에서 `python -I`로 source/export→reviewed-fit CLI와 실제 HTTP health/
  B0/B1/OpenAPI·본문 제한/기한을 검증했다. Starlette TestClient의 기존 deprecation 경고
  1개는 남아 있으며 실패를 숨기거나 필수 검사를 완화하지 않았다.
- 다음 우선 작업은 동일1개 fit 반복이 아니라 허용된 서로 다른 포장/상품군의 사실·정체성
  검수와 업무 DEMO 명시 매핑 확대다. 다중 상품/그룹에서 튜닝 전 고정한 독립 사실/관련성
  명세·기준선 비교를 확보한 뒤에만 품질·분리 평가를 확장한다. 원천 조건의 부족과 사용자/
  미래 로그 부재를 혼동해 대기하지 않는다.
- PR 생성·최신 head CI/Codex·미해결 지적 확인·병합/main CI·브랜치 정리는 조정자 인계 후
  진행하며 이 로컬 검증을 병합 완료로 표시하지 않는다.
