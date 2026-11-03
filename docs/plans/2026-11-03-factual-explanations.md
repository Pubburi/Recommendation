# R04 — 원래 기여와 실제 비교 사실의 opt-in 설명

main `3f0a6cf`의 B1은 feature/contribution·generic 이유 코드를 제공했으나 실제 값·비교
목표/단위와 활성 hard bound를 짧은 사실 이유로 표시할 제공자 계약은 없었다. 소비자가 같은
feature 해석을 복제하지 않도록 기존5개 B1 경로에 opt-in 설명을 추가한다. 새로운 endpoint·
점수 모델이나 기존 기능 오류라는 주장을 만들지 않는다. B0 baseline을 포함한 POST는6개다.

## 구현 전 고정

2026-11-03 13:47:55 UTC에 자체7상품의 명시 취향·기준 ID/그룹·가격/도수 hard 조건과
독립 후보/actual-target 사실을 동결했다. 도수/가격 실제0·unknown·미확인/빈 태그와 쉼표/
개행 atom을 구분한다. 명세 SHA256은
`5b5b93b0b2a473ec2ee7a928f194c023272201e1b1b5d4b80284fc05e3bad765`이다.
기존6개 POST의 실제 기본 응답 바이트와 새 옵션의 이전422를 보존했다. 점수 helper로 기대
사실/관련성 정답을 생성하거나 실행 결과에 맞춰 명세를 수정하지 않는다.

## 계약과 구현

[공식 설명 schema](../EXPLANATIONS.md)는 strict include_explanations=false 기본값과
true일 때만 생기는 item.explanation이다. 생략/false와 optional null은 필드 단위로
직렬화에서 빠지며 기존 nullable 필드·B0 계약은 유지한다. 직접 profile과 similar/context/
positive feedback의 실제 winning reference ID를 구분한다.

원래 양수 contribution의 actual/target·단위·고정 한국어 label과 실제 활성 hard 조건만
표시한다. 미확인 수치·비활성 상수/OOV/0점은 선호 이유가 아니다. 가격/가용성은 입력조건
근거이며 DEMO/실판매·재고 권위를 추정하지 않는다. atom을 쉼표/개행으로 나누거나 HTML/
LLM 본문·새 원천을 추가하지 않는다.

상위 최대3개 기여는 원 contribution 내림차순·component/feature 동점으로 고르고 전체
양수 개수/partial truncation을 표시한다. 원래 contributions 전체·합/score를 바꾸지 않는다.
실제 hard 근거는 최대4개, 설명 객체는 UTF-8 최대4096B다. label은 고정이며 실제 값을
잘라내지 않고 최종 reference ID를 반영한 뒤에도 상한을 확인한다. 기존 요청512KiB와
limit100·10초 수신/무모델 startup·요청 격리를 유지한다.

## 검증과 기존 근거 보존

기존 제공자 관련201개와 새 R04 회귀44개를 확인했다. 기본6개 POST의 동결 응답과 B1의
false 응답은 byte 동일했고 true에서 점수/순서/기여·fingerprint와 fit 횟수는 그대로였다.
고정 source·0/null·constant·hard bound·typed enum/discriminator·최대 atom/reference ID와
partial/4KiB·strict bool/null을 검증한다. 새 wheel에서는 실제5개 B1 HTTP와 기본/false·
OOV/baseline·literal atom·입력 오류를 비교했다. Python3.12.14/uv0.13.6의 전체 locked
검사는 실제 exit0으로 완료됐다. Ruff/check·format143파일, pytest948개(새44개 포함),
기존 B0/B1 고정 시나리오 각8/8과 새 sdist/wheel의 runtime-only 격리 CLI·실제 HTTP가
통과했다. 설치 wheel의 최종 complete/passed 기록은 2026-11-03 13:58:15 UTC다.

기존 container DEMO1 및 family-browse DEMO5의 두 전체 보고서는 **각 기록된 실행 시각의
오프라인 회귀 재생**에서 byte 동일했다. source11 cohort 전체 보고서도 byte 동일했다.
기존 M1 baseline/비교/재생 보고서도 파일 해시가 그대로이며 선택 실험을 새로 실행하지 않았다.
과거 snapshot을 현재 fresh export로 부르지 않으며 새 업무 API/DB 캡처·원천 획득이나
제품/학습 품질 증가분으로 집계하지 않는다. 원래 파일/모델·원문·로그는 ignored에 보존한다.

README 기존3사례/순서·부족1을 비교해 보존한다. 필수 이유 표시 증가분이며 더 강한 독립
서비스 장애/품질 근거로 미리 교체하지 않는다. 전체 R04/Backend/React·R02/AI03 완료가
아니므로5/20을 유지한다. 최신 head CI·완료 Codex·native 미해결0·Squash/main CI·
병합 브랜치 정리는 root의 별도 최종 게이트다.
