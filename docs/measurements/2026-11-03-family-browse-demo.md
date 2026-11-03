# 실제 상품군 browse DEMO의 고정 사실·B1 관측

기준 main `56e74fe`, Python3.12.14·잠금 sklearn1.9.1의 기존 B1을 사용했다. 기존 accepted
CC0 원문/검수의5상품군을 root 소유 전용 폐기 업무 API가 반환한 ID에 명시 연결했다.
분류 맥주·3000–3400원은 명시 업무 DEMO 권위이며 원천 판매가/가용성 관측이 아니다.
모델은 상품군의 실제 ABV와 업무 분류만 사용하고 이름/외부 본문·P31/P176/사진·맛/향을
추론 특성으로 추가하지 않는다. 관계/라벨은 원천 정체성/검수 결속을 확인하는 사실이다.

| 범위·관측 | 값과 해석 |
|---|---|
| 원천 입력/선택 | 기존 accepted6항목 중 product_family 검수·known ABV5. 신규 원문 수집0 |
| 실제 업무 매핑/export | 별도 owned_family_browse_demo/http_read의 명시5ID, B0/B1 각5행 |
| 데이터/fit scope | reviewed_source_family_browse_demo_only / known_mapped_family_browse_demo |
| 학습 행/수동 그룹 | 각5. 물리 SKU·개별 포장·판매/재고 승인이 아님 |
| TF-IDF | 업무 분류 category:맥주1어휘·IDF1.0 |
| ABV | 원문 exact vol%5관측/누락0, min5.3–max10.0, 기존 MinMax 거리 활성 |
| 용량 | 관측0/누락5, 양쪽 null 보존·거리 비활성 |
| 맛/향 | 각각null5/5, 검수 빈 태그0/5. 모르는 값을[]/추정값으로 바꾸지 않음 |
| 사실·제약/fallback | 사전 동결14개를 B0/B1 같은 후보/조건에서14/14 통과. 관련성 정확도가 아님 |
| 재현 | 같은 authority/snapshot/mapping/spec의 두 전체 보고서가 실행 시각만 제외하고 동일 |
| 관련성 지표 | 독립 선호/관련성 라벨 없음으로 미산출. 사용자·시간/상품군 holdout/품질 성과 없음 |

사실 명세 SHA256은 `9097128e5696ba71872708b1bb617bb82912863f8b6440ddb9dd4ea635d718a1`,
학습 입력 hash는 `e96c58b0044087b518f29b491272aa31b7ac1b48923a30f3885a9e0dbf312573`,
모델 fingerprint는 `0ef78f003462ff82ee84166f927dd27ef0e66315a5684fe61a9588742490621b`다.
원문·업무 응답/실제 ID·명세·모델·로그는 ignored에만 두고 공개 데이터셋으로 재배포하지 않는다.

별도 새 목적의 ABV=0·GTIN·can·양수 용량 발견 GET1회는 HTTP200·86B·0ID였다. 원천의
unknown을0으로 채운 것이 아니며 이 조건 결과를 전체 원천의 부족 추정으로 쓰지 않는다.
추가 Action 수집/재시도·aT/제조사 제한 우회는 없었다.

기존 physical container/GTIN/known-volume gate·source 후보1과 DEMO1의 전체 결과,
source11 B1/M1 보고서는 보존한다. 이번5개는 기존11상품군의 부분집합이며 source11+
DEMO1+5나 문맥11을 새 SKU 수로 합산하지 않는다. 일반 서비스 origin/불완전 매핑·unknown
보충은 거절한다. 실제 서비스 카탈로그/품질·전체 R02/AI03·Backend 자동 B1 연결은 미완료다.
수치 범위 활성/검사 수·실행 시간을 순위 개선이나 앱 성능 성과로 주장하지 않는다.
