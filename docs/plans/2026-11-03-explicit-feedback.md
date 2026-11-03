# R05 명시 피드백의 점수·제외 제공자

main `427fa88`의 content는 명시 profile과 hard 제외 ID만 받았고 positive/관심 없음 상품
입력을 받지 않았다. context는 장바구니 사실의 별도 제공자여서 개인 피드백의 negative 우선
정책을 대신하지 않는다. 기존 기능 오류로 바꾸지 않고 누락된 필수 R05 증가분을 구현한다.

## 구현 전 고정과 계약 선택

2026-11-03에 기존 content/context의 전체 응답 바이트를 보존하고 실제 TestClient 경로에서
feedback404·content의 feedback 필드422를 확인했다. 가상 상품13개의 사실·명시 취향·
negative unavailable 기준/가용 변형·positive unavailable/그룹·unknown 가격·hard 제외를
모델 결과와 독립적으로 동결했다. 후보5/6/9, winning positive1/3/profile, negative 제외2·
positive 제외6·평가2가 기대이며 명세 SHA256은
`16303a212e083b37105b14b41f5ffb95f397cd4d442a948a12ff93cf3291b570`이다.

공동 계약은 새 [POST /v1/recommendations/feedback](../FEEDBACK-API.md)로 확정했다.
기존 content/context wire와 B1 엔진을 보존한다. positive/관심 없음 각각 unique 최대20개
엄격 ID, 요청별1fit, profile·사용 가능한 positive의 기존 rank/similar 원점수 중 최대 양수,
동점 profile→작은 positive ID, 원기여/실제 이유를 선택한다. negative ID/알려진 그룹을
우선 제외하고 모든 알려진 positive 그룹도 대안 후보에서 제외한다. unavailable/missing
사실은 보완하지 않으며 negative와 충돌한 positive는 점수 자료가 아니다.

평가 가능한 positive와 지원 text/활성 수치가 있는 informative positive를 구분한다.
informative positive 모드는 양수 후보만 반환하고 부족분0점 채움을 하지 않는다. 정보가
없으면 원래 profile/B0 fallback을 보존하며 그0점 행은 baseline 출처로 표시한다. 후보가
없으면 두 경로 모두 empty/no_eligible_products다. 프로필을 합성해 태그 상한을 넘기거나
negative 벡터/평점 임계값·반복 횟수 가중치를 만드는 대안은 채택하지 않았다.

## 검증과 인계 범위

고정 독립 사실·조건과 원래 B1의 winning 점수/기여를 별도로 대조한다. negative의 같은 ID/
그룹 우선·known/unavailable 그룹·missing ID 무추론·unknown/실제0·null/[]·두 fallback·
1fit·top-K/동점·요청 순열/동시 격리와 경량 startup·기존 원문 경계를 검증한다. 새 wheel은
runtime-only 격리 설치 뒤 별도 authored HTTP 사실·원래 content/similar 증거·negative
충돌/빈 결과·입력 거절과 production10초 부분 본문408을 확인한다.

같은 동결13상품의 새 endpoint는200으로 응답했고 후보5/6/9·승자1/3/profile·제외2/6·
평가2가 모두 기대와 일치했다. 기존 content/context 전체 응답 바이트와 기존 B1/제공자·계약·
README·lock 등 동결9파일은 불변이다. Python3.12.14·고정 uv0.13.6/locked·offline의
`./scripts/check.sh`가 실제 exit0이었다. 저장소 검사·Ruff/포맷·pytest880개(새37개), B0/B1
자체 시나리오 각8/8, 새 sdist/wheel과 runtime-only 격리 설치·실제 CLI/HTTP를 통과했다.
이번 실행의 새 배포 보고서 complete/passed와 프로세스 종료를 확인했으며 이전 보고서를
재사용하지 않았다. 기존 TestClient deprecation 경고1개를 남긴다. 고정 사실의 기능 검증이며
테스트 수/CI 시간·404→200을 모델 품질/서비스 시간 성능 성과로 쓰지 않는다.

최신 head 필수 CI·완료 Codex 리뷰·native 미해결0·Squash/main CI·병합 브랜치 정리는
별도 최종 게이트다. 전체 R05·Backend/web 연결·서비스 품질은 계속 미완료다.

Backend는 본인 계정 피드백의 저장/수정/삭제·권한과 찜/평점→positive 계약, 최신 상품 상태
재확인을 소유한다. Recommendation은 현재의 명시 신호/사실만 점수화하며 사용자/미래 로그·
외부 평가자 확보를 기다리지 않는다. 기존 source11·DEMO1·문맥11의 grain/authority와 전체
보고서·기준선을 그대로 두며 이번 authored 입력을 서비스 카탈로그 fit·학습 품질로 세지 않는다.
MVP 기한2026-12-31과 인수 전 필수 우선·Jan 추가 개선/최종 중단 규칙을 유지한다.

README 기존3사례의 원인·실행 근거와 비교했다. 이번은 누락 제공자의 필수 구현이며 독립된
서비스/카탈로그 품질 문제의 더 강한 사례 근거가 아니므로 전체 README·3개 본문/순서·부족1을
보존한다. 구현 분량·테스트 수로 네 번째 사례를 만들지 않으며 원본/로그/모델은 Git에 올리지 않는다.
