# Checked catalog의 Backend 소비 연결

## 문제·선택과 동결

main `4358b6d`에는 원권위/완료4파일을 다시 확인하는 Python 반환값과 독립5B1 인수 CLI가
있었지만 Backend가 path+SHA로 pin해 소비할 공식 bundle/발행 CLI는 없었다. 새로운 모델이나
제공자를 추가하는 대신 기존 checked catalog·명시 mapping·원 업무 응답을 실제 소비 계약으로
연결한다. Backend는 원천 권위를 재구현하지 않고 현재 public fields와 조건/만료를 확인한다.

코드 전에 정확 top9/record7·fresh-only/원 snapshot+300초 예산, 원본 불변/부분 출력과 입력 변경
거절·무모델 producer 및 authored A/B/C 사실·기본순/제약/이유 시나리오를 고정했다. 새 CLI가
없다는 실제 module-help 결과도 지원 가용성 기준으로 보존했다. 과거 서비스 장애/오류율이 아니다.

root의 실제 ProductRequest 사전 검토에서 price는1원 이상·img는 nonblank였다. API 실행이나
DB 우회 전에 원래 authored A0원/빈 이미지 계획을 A1원과 명시 placeholder로 정정하고 원본/
정정 이력을 보존했다. B1000/C2000·ABV0/10/20·용량330/500/750과 unknown 맛/향은 유지한다.
실제 maxPrice1+maxABV0는 A, maxPrice0는 빈 후보로 동결했다. 이전 provider의 가격0 unit
경계 증거를 이번 실제 업무 등록 성과로 섞지 않는다. QID/GTIN 형태의 합성 schema fixture는
원천 관측/실제 할당이나 물리 SKU 증명이 아니며 authored origin을 명시한다.

## 구현·필수 검증

[공식 bundle 계약](../BACKEND-CATALOG-BUNDLE.md)의 producer는 기존 load_checked_export를
발행 전후 재사용하고 원 parsed Product7/features8·catalog/ID/group/unknown과3개 DEMO flag를
보존한다. 원 snapshot/mapping·권위/완료 산출물 hash가 달라지거나 남은 예산이 없으면 완료로
발행하지 않는다. 단일 bundle whole SHA를 receipt에 기록하고 기존 출력·예상 밖 target을 보존한다.

독립 검사는 catalog/record ID·순서/그룹·원 사실,0/null·고정 scope와 source key 유일성,
historical/승격/부적절한 상태/수·만료/입력 변조·실패 시 incomplete/미발행·기존 파일 보존과
무모델 import를 확인한다. 새 runtime-only wheel의 실제 producer CLI→기존 B0/B1 HTTP로
같은 검수 catalog의 고정 조건·이유를 확인하고 변조 export는 거절한다.

root는 공유 runtime을 소유한다. 별도 authored 상품을 실제 소유 업무 API로 생성하고 공개 GET
snapshot/명시 ID binding을 전달한다. 각 DB 검증 때 실제 snapshot에 맞춰 새 mapping/export/
bundle을 연속 발행하며 옛 snapshot의 시각만 바꾸지 않는다. source11·DEMO1·별도family5의
grain/보고서·기존7POST wire와 모델은 보존하고 카탈로그/품질 분모에 합산하지 않는다.

## 최종 패키지 검증과 발행 끝단

첫 후보의 전체1280검사와 새 wheel은 통과했지만 마지막 발행 계약의 통제2조건에서 link 중
만료 뒤 completed=true, 완료 receipt 작성 직후 OSError에도 true가 남는 것을 별도로 재현했다.
코드/hash와 원실패를 보존하고 완료 직전 시각 재확인·실패 시 승인 target 제거/미완료 receipt
정리를 보완했다. 같은 두 조건은 모두 completed=false·승인 bundle 미발행/제거다. 자연 서비스
장애율이나 기존 원천/모델 오류로 합산하지 않는다.

최종36개 집중 검사와 전체1282개(기존1246+신규36)·Ruff166파일·B0/B1 각8/8이 실제 exit0이었다.
새 sdist/wheel runtime-only python-I의 실제 CLI 발행→기존 B0/B1 HTTP·원업무 값/unknown과
고정 조건·변조 export 거절도 통과했다. 새 complete/passed는 2026-11-04 07:45:50 UTC다.
최종 wheel/source/locked runtime 요구사항은 별도로 hash 동결했고 중간1280/wheel은 최종
승인 근거와 분리 보존했다. 기존7POST 전체 wire·기존 명시 요청의 전체 응답과20개
API/core/model/export/원보고서·README hash는 그대로다.

## 실제 업무 소비의 첫 실행

별도 소유 업무 API로 생성한 authored3행의 실제 공개 Product7/features8·명시 ID/group을
받아 원 mapping/export와 fresh bundle3행 발행을 확인했다. 기존80행을 후보에 추가하거나
이름으로 ID를 찾지 않았다. 실제 bundle의 whole SHA·엄격 구조와 고정3상품 사실은 일치했다.

첫 Backend private caller는 guest401/로그인 뒤200 UNAVAILABLE을 반환했다. 최초 기록의
provider 전송0 추정은 카운터 관측 위치 때문이었고, 추가 진단에서 실제 POST 진입→3초 호출
기한의 UNAVAILABLE→늦은 provider200 순서를 확인해 정정했다. 기존 cold-budget 정책의
정상 동작이며 loader/권한/제품 결함이나 제품 수정 성과가 아니다. 원 추정·요청/응답 순서와
snapshot/mapping/export/bundle은 구분해 보존한다.

같은 소스의 별도 유효 profile(maxPrice1/maxABV0)과 hard price0 빈 결과는 원 B1 전체 응답과
일치했다. 이후 허용 집합 밖 주종의 PUT200을 가정한 harness는 실제400으로 실패했다. 이는
제품 결함이 아닌 시험 입력 오류이며 원본을 보존하고 허용된 사케 OOV·본인 NOT_STARTED
준비 조건으로 명세를 정정했다. 이 시점에는 공동 최종 인수·고정9조건 fit이 미완료였으며
원 snapshot의 시각을 바꾸거나 만료된 원본을 재사용하지 않았다.

## 남은 작업·README 판단

이 bundle은 service_catalog_approved=false의 입력 소비 증분이며 일반 legacy80/서비스 SKU·
새 source·권리·사용자 만족도·순위/성능 개선·전체 R02/R04/AI03 완료를 주장하지 않는다.
Backend의 실제 caller와 현재 계정/취향·후보 재확인/fallback·React, 허용 현재 카탈로그의 전체
필드/권리·명시 mapping과 실제 fit·독립 평가 인수가 남는다. 사용자/미래 로그를 기다리지 않는다.

README 기존 CS05/06/07의 원천 오류·입력 의미·수량→학습 문제보다 강한 독립 서비스 영향
근거는 새로 얻은 것이 아니므로 기존3사례/순서·전체 본문과 부족1을 유지한다.
