# Backend 저장 취향의 기존 B1 입력 연결

## 범위와 코드 전 기준

main `5723f81`에서 기존 R06만 Backend GET 저장 취향 shape를 직접 받았고 content/exploration/
feedback은 별도 profile/constraints가 필요했다. 같은 저장 soft/hard·unknown/0을 각 소비자가
다시 임의 매핑해야 하는 연결 경계를 작은 입력 증분으로 완성한다. 새 모델/endpoint·자동 업무
매핑·원천 수집/DB 변경은 없다. 전체20개 MVP의 2026-12-31 기한과 현재7/20은 그대로다.

구현 전에 authored 사실·세 경로별 신규 요청/기존 명시 요청·예상 ID1/적격1·fallback 없음,
raw정밀도·충돌/정규화·unknown/0·fit 계약을 동결했다. 소유 ephemeral loopback 실제 HTTP에서
새 필드는3/3 422, 대응 기존 입력은3/3 200과 고정 사실을 통과했다. 이전 정상 제공자 장애나
서비스 추천 품질 성과가 아니다. 기존7POST 전체 응답과 core/model/export·기존15원본 해시도
동결했다. 원문/모델·비공개 보고서는 추적하지 않는다.

## 구현과 필수 검증

기존 BE-shaped DTO와 B1 engine을 재사용하며 opt-in 입력을 명시 profile과 동시에 받지 않는다.
soft는 soft로, hard는 교집합으로 연결한다. 요청 snapshot null/[]·실제0을 보존하고 SKIPPED/
NOT_STARTED는 원래 cold fallback이다. literal을 변형/드롭하는 변환과 hard 충돌은 fit 전에422다.
새 입력만 원문 Decimal을 다시 검증하고 sync engine/thread pool·기존 일곱 POST wire를 유지한다.

독립 authored 명시 요청과 전체 응답/1fit 동등성, 원자 tag/0·네 방향 hard 교집합·negative/group/
positive 승리 출처·빈/OOV fallback, 완전 shape/동시 profile·정밀도/큰 지수·Unicode 손실 거절을
검증한다. OpenAPI·경량 startup/빈 요청과 기존512KiB/중복/malformed 순서를 확인한다.
새 runtime-only sdist/wheel은 python -I의 실제 세 HTTP에서 동등 요청·SKIPPED·충돌·literal·
raw정밀도·413와 production10초 부분 본문408을 확인한다. 전체 locked/Ruff와 기존 원천/
DEMO 보고서·7POST wire 보존을 확인한 실제 결과는 완료 후 기록한다.

## 실제 실행 결과

같은 세 새 요청은 모두200이며 독립적으로 작성한 기존 profile/constraints 요청의 전체 응답과
byte 동일했다. 기존7POST 전체 응답·원래 검수11조건의 두 historical 재생 전체 case·15개
core/model/export/원래 source11·DEMO1/5 보고서와 README 해시는 그대로다. 신규 입력의
지원 전422를 과거 서비스 장애·오류율 개선으로 표현하지 않는다.

Python3.12.14/uv0.13.6 locked/offline `check.sh`는 actual exit0이었다. 전체1246개는 기존1141+
새105개이며 별도 선행169회귀를 중복 합산하지 않는다. Ruff/format161파일·B0/B1 각8/8과
새 sdist/wheel runtime-only python-I 실제 CLI/HTTP·OpenAPI·세 opt-in 부분본문408이 통과했다.
최종 complete/passed 기록은 2026-11-04 02:17:25 UTC이며 wheel의 변경5모듈은 검사한 소스와
동일하다. 초기 설명 enum을 잘못 적은 authored3조건의 실패 원본은 보존하고 기존
`taste_match` 계약으로 정정했다. 후보·가격/도수 사실·기존 제공자를 결과에 맞춰 바꾸지 않았다.

## 인계와 남은 필수 작업

이 증분만으로 Backend의 본인 권한/현재 저장 취향·가용성 재확인·B1 호출/장애 fallback이나
React 연결·전체 R02/R05/R08/AI02를 완료 처리하지 않는다. 현재 권리/필드·서비스 카탈로그/
명시 mapping과 실제 서비스 데이터 fit·평가 부족은 그대로 남는다. 실제 사용자를 기다리지 않는다.
README CS05/06/07의 원천 상태·추천 입력 의미·수량→학습 정합성보다 강한 독립 서비스
영향을 확보한 것은 아니므로 기존3사례/순서·전체 본문과 부족1을 유지한다.
