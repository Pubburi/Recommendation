# DAT01/02 — 구조화 포장 식별과 수동 검수 경계

- 기준 `main db05e9c`, 작업 `codex/package-identity-audit`, Recommendation 단독 쓰기다.
  데이터/모델 상세는 이 레포, Backend 업무 상품/ID는 Backend 소유다. root는 기획·공통 검증·PR
  최신 리뷰/CI·병합/main CI·브랜치 정리·lease 해제를 담당한다.
- 기존5상품군 fit·같은 HTTP fixture를 반복하는 대신 실제 허용 구조화 데이터의 GTIN/단위·
  개별 포장 식별을 진행한다. 수집 전에 공식 CC0·WDQS GET·GTIN/수치/class 범위를 확인하고
  고정 LIMIT10 query1회 뒤 기존 collector로 ID4개만 GET했다. maxlag5·프레이밍/바이트/시간·
  정확 ID/revision 제한을 유지했다. 비용/계정/키·이미지/외부 리뷰·외부 연락·GS1 조회·aT 특정
  자동 승인 거절 재시도/우회·OFF 폼/수집은 하지 않았다.
- 실행 관측: discovery HTTP200·561B·4ID, versioned collector HTTP200·39,892B·4item.
  신규3개와 기존 브랜드1개이며 판매 SKU4개가 아니다. checksum 통과4/4 claim, 같은 item의
  용기/라벨/단일GTIN/용량/도수 조합1/4이며 그1개는 브랜드/container 혼합이다. 용기/용량
  unknown 각3/4, ABV/라벨 unknown 각1/4, GTIN reference 없는 claim4/4다. 조회 성공·
  바코드 integrity·개별 포장·합법 판매/Backend 매핑을 각각 구분했다.
- actual raw/receipt 해시와 exact revision URL을 결속한 수동 검수4개는 모두 hold다. 혼합
  grain, 상품군/브랜드, 라벨/단위/용량 부족을 구분했고 제조사/묶음수는 unknown으로 남겼다.
  식별 미완료를 이유로 도구 전체를 기다리거나 실제 값을 만들어 채우지 않았다. 매핑/fit승격0,
  신규 서비스 카탈로그 SKU0·서비스 B1 품질 미완료다.
- 구현: `collection_snapshot`으로 accepted·모드/HTTP·CC0·manifest 모델/원문 해시·정확ID/revision
  gate를 경량 재사용한다. source_family_experiment 기존 검증 함수를 이 gate에 위임하며 fit/
  rank/HTTP는 변경하지 않는다. 새 `package_identity_audit`는 GTIN 문자열/검증 숫자·allzero·
  선행0/canonical 비교·qualifier/다중/중복·명시 container와 단위/unknown·혼합 grain을 감사한다.
  수동 후보도 기존 보류를 덮거나 Backend ID/fit 승격을 만들지 않는다. 원본/receipt/review는
  ignored, 공개는 도구/자체 fixture·집계/조건/한계다.
- 출력은 새 ignored 디렉터리와 완성 receipt로 구분한다. 변경/미승인 snapshot·수동 검수 해시/
  revision 불일치·기존 경로를 거절하며 원문/개인 경로를 진단에 복사하지 않는다. 알고리즘 version과
  실행 코드 커밋을 기록하고 새 projection을 기존 검수 완료로 자동 재사용하지 않는다.
- 독립 authored 회귀는 타입/길이/ASCII·checkdigit/allzero/선행0·qualifier/deprecated/다중 식별자·
  혼합grain/공유키·단위/수치 unknown·review/hash/revision·실제 CLI 출력/보존/고정 진단을 확인한다.
  새 wheel runtime-only `python -I`도 자체 collector 재생 receipt와 package CLI를 실행한다.
  실제 원천·개별 카탈로그/학습 파라미터는 CI에 전달하지 않는다.
- README 현재2/4·순서를 유지한다. 실제 포장 식별 근거는 늘었지만 현재 REC-CS05 수집 신뢰성/
  후보 REC-CS04 데이터 경계와 겹친다. 아직 실제 Backend 상품/추천 결과의 독립 영향이나 품질
  근거가 없어 새 세 번째로 쪼개지 않는다. 공개 원천 모델 표현 학습·serviceSKU·추천 관련성/사용자
  선호 품질도 혼동하지 않는다. [계약/관측](../PACKAGE-IDENTITY-AUDIT.md)에 근거를 보존한다.

검증·코드 검토·최종 head/PR 근거는 실행 후 아래에 기록한다. 지연/최적화 작업이 아니므로
API/모델/브라우저의 가상 성능 수치나 실측되지 않은 감소율을 만들지 않는다.

## 독립 검토의 입력 경계 수정

- Backend 담당자의 읽기 검토로 새 포장 감사가 기존 scalar 정규화의 permissive 수량 rank/type을
  그대로 믿는 경계를 발견했다. 자체4입력(ABV/volume × 잘못된 rank/type)은 수정 전5/500을
  값으로 남겨 회귀가 실패했다. 새 감사에서 quantity 타입·normal/preferred·value snak·문맥을
  확인해 unknown/hold로 만들고 수동 후보 우회도 차단했다. 실제4원천에서 발생한 결함은 아니다.
- 같은 독립 검토에서 unit suffix만 같으면 bare QID/외부호스트도 단위로 해석되는 경계를 찾았다.
  자체4입력의 수정 전 오인(ABV5/volume500)을 재현하고 canonical Wikidata http(s) 단위 URI만
  허용하도록 보강했다. 정상 http/https와 실제4원천은 유지한다. 기존 catalog/source-family/
  HTTP 모델의 해석은 바꾸지 않고 새 포장 식별의 승인 근거를 더 엄격하게 제한했다.
- 첫 전체 검증은388회귀·B0/B1 각8계약과 새 wheel runtime-only 기존/신규 CLI·실제 health/
  B0/B1/OpenAPI·10초 부분본문408까지 통과했다. 이후 URI 보강 때문에 이 결과를 최종 head에
  재사용하지 않고 관련/전체 검증을 다시 수행한다. 기존 TestClient deprecation1건은 남아 있다.
- 최종 `check.sh`는 저장소/locked·Ruff·pytest393·B0/B1 각각8/8과 새 sdist/wheel runtime-only
  기존 CLI/상품군 실험·신규 포장 감사 CLI·실제 health/B0/B1/OpenAPI·production10초 부분본문
  408을 통과했다. 기존 TestClient 경고1건은 동일하다. 모델/데이터나 외부 계정 없이 동작하며
  공유8000/DB를 사용하지 않았다. 이 검증을 앱 성능/사용자 추천 품질로 환산하지 않는다.
- 최종 projection을 이전 수동 검수의 사실과 별도로 대조했다. 라벨/revision·GTIN·분류·관측
  수치는 같고 일반 percent1항목의 기존 ABV unknown에 statement-review 보류 사유만 추가됐다.
  실제 원천의 오류가 줄었다거나 값이 새로 관측됐다는 뜻이 아니다. 변경 코드 해시와 대조
  결과는 ignored에 보존했고 수동 보류4/4·매핑/fit0을 확인했다.
- 구현/로컬 검증까지 완료했으며 PR 생성·최신 head Codex/필수 CI·병합/main CI는 아직
  조정자의 최종 게이트가 필요하다. 최신 PR 근거는 병합 후 연결한다. DAT01/02 전체와 서비스
  SKU/매핑·B1 데이터 fit·관련성/최종 평가의 미완료는 유지한다.
