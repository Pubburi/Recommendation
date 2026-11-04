# 허용 상품군1개의 정제·업무 매핑·실제 fit

기준 main `1d7fbde`. 필수 MVP의 데이터·실제 모델 적용을 진행하며 새 provider/검사기·
선택 모델 실험을 추가하지 않는다. 20MVP의2026-12-31 마감과 미완료 필수 작업 우선 원칙은
그대로다. [실행 관측과 분모](../measurements/2026-11-04-reviewed-family-application.md)에
수집 실패·실제 새 적용·두 DB 재현과 한계를 분리했다.

## 실행 단위와 실제 결과

1. 공식 CC0/접근 조건 확인 후 맥주 외 와인/시드르·제조자·ABV의 새 목적/쿼리·최대6개·
   GET1회·시간/바이트·오류/빈 결과 무재시도를 먼저 동결했다. discovery는6후보를 반환했지만
   원문 수집은 api_maxlag/accepted=false로 중단했다. 신규 live 수집 성공은0이다.
2. 기존 accepted4후보 중 포장/용량 부족으로 container로 적용하지 않은 상품군1개를 새
   family curation으로 검수했다. 정상 관계·정확 라벨/언어/revision·vol%5.2와 volume=null을
   결속했다. 다른3항목 보류와 원래 container gate는 그대로이며 raw GTIN은 승격하지 않았다.
3. 업무 snapshot 검증/fit 전 독립 사실·제약/fallback12조건을 고정했다. root 소유 두 DB의 별도 시연 행을
   실제 API ID와 전체 응답 hash로 각각 명시 매핑하고 freshness 안에 기존 export/fit CLI를
   실행했다. 각12/12 통과,1상품군/1그룹·1어휘와 known 상수ABV/unknown 용량을 확인했다.
4. 두 모드의 fit 요약·모델 지문·case 전체 결과·관련성 미산출 상태는 같다. 같은12조건의 재현을
   24개 독립 정답으로 세지 않는다. 기존 source11·DEMO1·family5 보고서/모델·API·README를
   보존했고 원천/모델/실제 응답/로그는 추적하지 않았다.

## 다음 필수 계약

현재 container-only Backend B1 소비자는 이 family를 받지 않는다. family 기반 탐색이 MVP
R02의 허용 후보 단위가 되려면 별도 browse opt-in·scope/DEMO 표시·unknown 용량·현재 업무
재검증과 Backend/React 소비를 공동 계약으로 결정해야 한다. 물리 포장 증거가 없는 family를
일반 container/판매·장바구니 SKU로 자동 승격하지 않는다. 실제 허용 현재 카탈로그 확대와
독립 사실/누수/fallback/재현 인수는 계속 필수이며 전체 R/AI 완료나 사용자 품질을 주장하지 않는다.

## 검증·README 판단

실제 정제1·두 별도 fresh export 각1·기존 B1/B0의 동일12조건·정확 수치/unknown과 재현 비교를
확인했다. 구현 변경이 없어 새 회귀/성능 실험을 억지로 만들지 않는다. 문서의 상대 링크·관측값/
hash와 기존 소스95파일·보고서/README20파일 보존을 확인하며 필수 remote CI는 유지한다.

이번 작업은 미적용 실원천의 새 업무 DEMO 적용이다. 기존 README CS05(원천 오류),
CS06(HTTP 입력 의미), CS07(수량→학습 정합성)보다 강한 독립 문제 해결 사례로 선정할 근거는
없으므로 세 본문/순서·whole bytes와 부족1을 유지한다. 단일 후보/검사 수를 네 번째 사례나
성능·추천 품질로 바꾸지 않는다. 추가 모델/튜닝·주변 감사·독립 네 번째 사례 확보는 MVP 인수
이후2027-01-01부터이며, 미완료 필수 작업을 뒤로 미루지 않는다.
