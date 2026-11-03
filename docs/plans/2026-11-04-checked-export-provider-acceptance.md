# 검수 export 산출물의 실제 소비와5B1 HTTP 인수

main `17a99e3`의 business_export는 검수된 B0/B1 요청과 완료 receipt를 만들지만, 소비자가
원권위와 실제 요청 파일을 다시 대조해 로드하는 경로는 없었다. reviewed_catalog_fit는 local
B0/rank를 검사했고5B1 HTTP는 authored 입력으로 각각 검증했다. 이번은 두 경계를 잇는
checked loader/독립 실행 CLI다. 요청별 fit 설계에 지속 모델 복원이 없다는 점을 결함으로
만들거나 과거 서비스 장애·새 provider를 주장하지 않는다.

## 구현 전 고정과 정정

2026-11-03 23:24:49 UTC에 기존 검수 상품군 browse DEMO5의 사실·그룹/실제 업무 매핑과
content/cold/OOV/hard 빈 결과·similar·context 기준 동점·negative 제외·exploration의11개
독립 기대를 고정했다. 원래 명세 SHA256은
`d1f38c56aca68f31904ae086ed968f0f0c8a75a6b4d5129d010a013d44be9fd4`다.
후보/순서·기준 key는 scorer 결과로 생성하지 않았으며 맛/향/용량은 원래 unknown이다.

기존 원천의 명시 ABV/업무 DEMO 분류·가격만 사용한 실제 HTTP 첫 재생에서 후보·eligible·
fallback·비교 출처는11/11 일치했다. all-negative의 빈 후보를 fit 없음으로 선언한 초기 metadata
기대 한 개는 기존 계약과 달랐다. nonempty request catalog를 fit하므로 true/같은 지문이
정상이다. provider를 수정하지 않고 원래 실패와 명시 정정을 보존했다. 후보/사실/순위 정답은
바꾸지 않았으며 코드 구현 전 정정한 명세의 SHA256은
`25415a893f7756bf95af6981e87ee5840c165e2845cf924953db534e831ca5cf`다.

## 실제 소비 계약과 관측

[공식 계약](../CHECKED-EXPORT-ACCEPTANCE.md)은 기존 writer를 바꾸지 않고 원authority/
mapping/snapshot·기록 시각과 완료4파일의 exact bytes를 대조한다. 기본 모드는 현재 freshness,
명시 replay는 당시 유효했던 과거 DEMO만 허용하고 model_loaded/service_catalog_approved=false다.
실제 source-backed DEMO5의 오래된 export는 기본 CLI에서 exit2/출력 미생성으로 거절했다.
같은 checked catalog를 기존5B1 HTTP로 전달한 명시 historical replay는11/11을 두 번
actual exit0으로 통과했고 case 전체 요청/응답·issues/판정은 동일했다. 기존 fit 지문도 같다.

이는 새 fresh 업무 캡처/새 원천·제품/SKU 확보가 아니다. container DEMO1/source11·별도
family DEMO5의 grain/권위와 원래 보고서는 그대로다. 새로운 모델·원문/파라미터 복원이나
서비스 adoption·사람 선호·시간 성능 성과로 집계하지 않는다.

## 검증·인계

회귀38개는 완료/부분·symlink/원문 바이트/권위 hash·stale/future/replay 구분, 동결 사실과
실제5B1 응답 변조, 실행 중 파일 변경/만료와 완료/통과 분리·무모델 import를 확인했다.
새 wheel은 별도 authored3상품군의 기존 실제 export/fit 지문을 사용해 fresh checked CLI→
실제5B1 HTTP, 명시 replay·변조 거절/출력 미발행을 검증한다. 실제 검수5상품군의11조건과
CI authored5조건을 품질/데이터 수로 합산하지 않는다. Python3.12.14/uv0.13.6 locked/offline의
전체 check.sh는 actual exit0이었다. pytest1054개(새38개), Ruff154파일, 기존 B0/B1 각8/8과
새 sdist/wheel runtime-only python -I·CLI/실제 HTTP가 통과했다. 새 배포 complete/passed
기록은 2026-11-03 23:38:14 UTC다. 기존7POST 전체 응답과 원래 export/모델/보고서·README
15파일은 byte/hash 동일했다. 이전 PR의 격리 실행 경고1개는 유지한다.

README CS05/06/07의 실제 원천 상태·추천 입력 의미·수량→학습 실패보다 강한 독립 서비스
원인/영향을 확보한 것은 아니므로 기존3사례/순서·전체 본문과 부족1을 유지한다. Backend
본인 취향/계정·현재 업무 재확인·B1 소비/React와 전체 R02–R08·AI03 인수는 남는다.
완료6/20을 올리지 않으며 최신 head 리뷰/CI·native0·병합/main CI·브랜치 정리는 root가 확인한다.
