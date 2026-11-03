# 실제 검수 상품군의 별도 browse DEMO 매핑·B1 fit

main `56e74fe`에서 기존 accepted4항목의 container 후보는 이미 연결한1개뿐이었다.
나머지3개에는 용량/용기 또는 라벨/도수가 부족해 기존 gate로 추가 curation할 수 없었다.
2026-11-03의 새 목적은 종전 양수 도수 발견에서 빠진 명시 ABV=0·GTIN·can·양수 용량의
조합이다. 공식 WDQS에 LIMIT10/단일 GET을 보내 HTTP200·86B·0ID를 받았다. 조건의 목적
표본이며 전체 원천의 부재 증거가 아니다. 재시도/임계 완화·Action 원문 수집은 하지 않았다.

## 승인 범위와 구현 전 사실

사용자 범위 안에서 root가 **reviewed_source_family_browse_demo_only**의 별도 폐기 업무
DEMO를 승인했다. 기존 accepted 원문6항목 중 product_family로 검수한 known-ABV5개만
선택하며 brand/unknown-ABV와 다른6상품군을 포함하지 않는다. 원천 라벨과 도수5.3–10vol%는
원래 hash/revision/vol%에서 확인한 사실이다. 용량·맛/향·포장/GTIN 할당은 unknown이다.
물리 포장/SKU·판매·재고/서비스 카탈로그 품질이나 전체 AI03 완료를 주장하지 않는다.

원천·검수 해시와 라벨 언어/revision/P31/P176/수량 사실을 먼저 고정했고 root의 명시 업무
분류/DEMO가격과 Product7/features8 입력을 분리했다. 모델 fit 전에 cold/category·실제 도수
범위·unknown 용량/OOV·가격/도수 포함 경계·제외/빈 결과·limit의14사실 조건을 동결했다.
명세 SHA256은 `9097128e5696ba71872708b1bb617bb82912863f8b6440ddb9dd4ea635d718a1`이다.
기대 후보/개수와 사실을 생산 점수/필터로 만들거나 이후 모델 결과에 맞추지 않는다.

## 필수 데이터 경계

[별도 curation/authority](../FAMILY-BROWSE-DEMO.md)는 원래 accepted receipt/raw/manifest/
review·선택 kind·정확 사실을 재검증한다. 기존 포장 `source_catalog`는 수정하지 않으며
family scope/type와 수동 고유 그룹·field provenance를 분리한다. 기존 export/fit CLI에
명시 family-review loader를 연결하고 원천/업무 양쪽 volume=null만 이 범위에서 보존한다.
새 원천 권리 승인 flag나 모델 복제·선택 최적화는 추가하지 않는다.

실제 허용 원천의 업무 snapshot은 root 전용 폐기 API의 owned_family_browse_demo/http_read다.
명시 실제 반환 ID/전체 응답·snapshot hash·5분 freshness와 모든 선택의 one-to-one 매핑을
요구한다. 원래 라벨/known ABV 일치와 미확인 volume/description/taste/aroma null을 유지하고,
무매핑/부분 매핑·container/일반 서비스 origin 혼합·수량/태그 보충은 거절한다. 가격/분류와
탐색 가용성의 DEMO 권위는 실판매 관측이 아니다. 기술 sku_group도 상품군 그룹일 뿐이다.

기존 B1 실제 fit과 B0/독립 사실·제약 검사기를 재사용한다. known-catalog 표현이며 학습/
holdout 분리나 사용자 선호 관련성 정답을 만들지 않는다. source11/문맥11·기존 container
DEMO1의 전체 결과는 보존하고 이번5개를 신규 수집/물리 SKU 수에 합산하지 않는다.

## 검증·README·인계

회귀는 원천 권위/정확 사실·실제0/unknown·브랜드 거절·미래/중복 그룹·owned origin·전체
매핑·미확인 필드 보충/혼합 거절, 기존 fit1회와 사실 모순의 fit 전 거절을 확인한다. 새 wheel은
별도 authored3가족의 실제 curation/export/fit CLI와 원래 HTTP·서비스 startup을 검증한다.
실제 업무 매핑/fit·재생과 전체 잠금 검사의 관측 결과는 실행 후 기록한다.

실제 root 전용 폐기 업무 API가 반환한5개 ID에 매핑해 B0/B1 각각5행을 export했다.
같은 raw/receipt/review/curation과 fresh snapshot·명시 매핑/동결 spec으로 기존 B1을 두 번
실행했고14/14 사실 검사를 각각 통과했다. 전체 fit 보고서는 executed_at_utc만 제외하고
동일했다. TF-IDF는 업무 분류1어휘/IDF1, 실제 ABV5관측·범위5.3–10vol% 활성, 용량
관측0/누락5·비활성, 맛/향 각각null5·빈 배열0을 확인했다. 상세 [원값](../measurements/2026-11-03-family-browse-demo.md)을 남긴다.

Python3.12.14·고정 uv0.13.6 locked/offline의 전체 `./scripts/check.sh`는 실제 exit0이었다.
저장소/Ruff·포맷·pytest904개(새24), B0/B1 자체8조건씩·새 sdist/wheel runtime-only의
기존/신규 실제 CLI·기존 health/B0/B1/exploration/similar/context/feedback HTTP·production
10초 부분 본문408이 통과했다. 이전 파일과 구분해 이번 실행의 complete/passed 배포 보고서와
프로세스 종료를 확인했고 기존 TestClient deprecation 경고1개는 유지한다. 기존 container
source_catalog·DEMO1/source11 B1/M1 전체 결과·README를 보존했다. 최신 head 리뷰/필수 CI·
native 미해결0·Squash/main CI·양쪽 병합 브랜치 정리는 root의 별도 최종 게이트다.

README의 기존3사례/순서·부족1을 비교해 보존한다. 이번은 필수 MVP의 실제 데이터 연결
증가분이며 더 강한 독립 서비스 문제의 원인/해결 근거로 미리 교체하지 않는다. 권리/필드가
부족한 서비스 SKU/관련성·Backend B1 자동 연결과 전체 R02/AI03은 계속 미완료다. 원문·
snapshot·명세·모델·로그는 ignored에만 두며 사용자/미래 로그를 기다리지 않는다.
