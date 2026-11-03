# R06 — 명시 선택과 실제 검색조건을 함께 반환

main `2fa1313`에는 기본/B1 6개 POST가 있으나 R06 검색 문구·조건 제공자는 없었다.
기존 R01 soft/hard 취향과 Backend의 정확 type/범위·반복 태그 AND를 연결할 경량 제공자를
추가한다. 기존 모델 결함·신규 원천/서비스 품질 성과로 표현하지 않는다.

## 구현 전 명세

2026-11-03 19:24:15 UTC(11-04 KST)에10개 자체 명시 입력의 기대 query/빈 fallback·0/null/
known empty·주종8분기/생략 수·원문 atom/UTF-16 경계를 고정했다. 명세 SHA256은
`d9e5492de919582a61e46790d792a3870c5104a8b4f01bf0c44dae39a0bc19ac`이다.
ASGI 요청의 새 경로10/10 HTTP404와 기존6POST 응답 전체·모델/원래 보고서·README11파일 해시를
동결했다. 기대 조건은 생산용 변환 helper나 점수로 생성하지 않았다.

## 선택한 계약

[공식 API](../SEARCH-PHRASES-API.md)는 Backend GET data와 같은 필수 nullable shape와 별도
search_opt_in_fields=[]를 받는다. soft를 자동 hard로 올리지 않고 선택한 facet만 AND로
묶는다. 모든 hard 범위를 유지하며 exact type 때문에 주종별 최대8문구·표시 limit5로 나누고
생략 수를 명시한다. 선택한 값의 unknown/empty나 hard 밖 목표는 빈 사유를 반환한다.

고정 짧은 label enum·typed 조건/순서 있는 최대45 query pair를 제공하고 상품 수는 미계산 null이다.
이 경로만 원문 Decimal scale≤2를 확인하며 실제0·ASCII 정밀도·원문 atom을 보존한다.
태그는 UTF-16/확정 ASCII·원문 중복만 검증하고 Java17 Unicode 정규화를 Python으로 동일하다고
추정하지 않는다. 선택한 non-ASCII에는 Backend 재검증 진단을 반드시 남긴다.

## 실행과 한계

새 제공자50개 회귀에서 독립 query·모든 hard/opt-in·태그/수치·문구 상한·정확 source shape·
수신/중복 JSON 경계·OpenAPI·무모델 startup을 확인했다. 개발 중 최초 OpenAPI default 표기가
빠진 검사를 수정했으며, 새 구현의 signed -0.00 query가 음수 ASCII가 되는 edge도 실제500을
확인한 뒤 실제0.00 유지/회귀로 보완했다. 기존 main 결함의 과거 성과로 집계하지 않는다.

동결10조건은 실제 기대 query/fallback10/10이며 기존6POST 전체 응답 바이트가 같다.
원래 model/contracts/source와 container DEMO1·source11 B1/M1·family browse DEMO5 보고서·
README11파일 해시를 유지한다. 새 수집·카탈로그/업무 캡처·서비스 카탈로그 fit/선택 실험은 없다.
Python3.12.14/uv0.13.6 locked 전체 check.sh는 actual exit0으로 완료됐다. Ruff150파일과
pytest998개(새50개 포함), 기존 B0/B1 고정 시나리오 각8/8, 새 sdist/wheel의 runtime-only
python -I·CLI/실제 HTTP·원문 scale422/413·production10초 부분 본문408을 통과했다.
처음 전체 실행은998검사 뒤 자체 loopback bind의 sandbox 권한 오류로 exit1이었다.
그 기록을 보존하고 승인된 자체 임시 포트 권한으로 동일 전체 검사를 다시 통과했다.

Backend의 본인 취향 전달·Unicode 최종 재검증/400·React 문구 선택과 실제 검색조건 연결·빈 결과
인수는 미완료다. 제공자만으로 R06/AI02나 MVP 완료 기능 수를 올리지 않는다. README CS05/06/07
세 사례보다 강한 독립 장애/서비스 영향 근거는 없어 기존3사례/순서·전체 본문과 부족1을 보존한다.
최신 head 필수 CI/완료 Codex·native 미해결0·병합/main CI·양쪽 브랜치 정리는 root의 최종 게이트다.
