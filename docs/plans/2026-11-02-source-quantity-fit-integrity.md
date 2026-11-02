# 원천 수량의 정규화·학습 입력 정합성

## 구현 전 고정한 문제와 범위

- 기준 커밋: `38b32b8`. 기존 `scalar_quantity`는 단위 문자열의 마지막 `/` 뒤만 읽고
  명시된 snak property/datatype·datavalue type의 모순을 확인하지 않는다. 다른 호스트나
  bare ID의 동일 접미사가 수치 관측으로 바뀌어 기존 source-family fit까지 전달될 수 있다.
- DAT02·AI03의 기존 원천→특성 경계를 수정한다. 새 endpoint·원천·업무 매핑은 추가하지 않는다.
  실제 확보한 상품군 원문·영수증·검수·동결 명세는 읽기 전용으로 보존한다.
- 구현 전에 별도 ignored 명세에 기준 커밋·10개 허구 손상 조건·독립 기대값·원천 파일 해시를
  고정했다. 단위 7종(bare ID, 외부 호스트, 호스트 접미사/사용자 정보, 비HTTP,
  scheme 생략, 다른 경로)과 명시 property/datatype/value type 모순 3종이다.
  상품군 3개 중 2개 fit·1개 transform 조건에서 학습 Q1의 수량만 각각 손상시킨다.

## 선택과 완료 조건

[Wikibase JSON 공식 명세](https://doc.wikimedia.org/Wikibase/master/php/docs_topics_json.html)는
단위를 URI로 나타내며 snak의 property가 해당 statement의 property와 일치해야 하고
수량의 value type을 `quantity`로 정의한다. 이 저장소의 지원 단위에 해당하는
`http(s)://www.wikidata.org/entity/…`만 변환한다. URI를 fetch하거나 접미사로 추정하지 않는다.
기존 최소형 입력의 생략된 중복 메타데이터는 허용하되 명시된 모순은 unknown으로 보존한다.

1. 변경 전 실제 offline 수집 영수증/검수/hash를 만든 허구 입력을 기존 fit CLI에 보내
   잘못된 수치 관측·모델 보고서 발행 여부를 기록한다.
2. 수정 후 같은 입력의 거짓 수치 사실 선언은 fit 전에 거절하고 보고서를 발행하지 않는다.
   사실을 `null`로 선언하면 기존 CLI가 나머지 관측 하나(15)만 사용하며 상수 열을 비활성화한다.
3. canonical HTTP/HTTPS 단위, 실제 0 도수와 기존 범위·문맥·다중값/deprecated 정책을 보존한다.
4. 실제 11상품군·5fit/6transform의 기존 동결 명세를 재실행해 전체 보고서와 fingerprint가
   기존 결과와 같은지 확인한다. 신규 서비스 카탈로그 fit·사람의 선호 품질로 해석하지 않는다.
5. 의미 있는 회귀와 기존 전체 검사·새 sdist/wheel의 runtime-only `python -I` CLI/HTTP를 확인한다.

분모는 사전 선언한 손상 표본 10개다. `n/10 → m/10`은 정확성 실험이며 실제 원천 발생률,
자연 오류율, 서비스 성능이나 사용자 만족도를 뜻하지 않는다. 시간 측정·성능 개선 주장은 없다.

## 실행·인계

- 구현 전 동결: 2026-11-02 06:54:00 UTC, ignored 명세 SHA-256
  `bc00f3fb04c283185398ca186768a228d1cb8612ffd30b2a7ef960bb904b1d99`.
- 실제 기준 실행: 06:55:05 UTC 완료. 손상10/10이 수치5로 정규화됐고 실제 CLI가
  2관측/min5/max15의 활성 수치 fit/report를 승인했다. offline collector receipt/검수/hash를
  새로 결속해 파일 stale/hash 실패와 구분했다.
- 구현: 정확한 URI 변환표를 scalar/package/context가 공유한다. scalar에서 명시
  property/datatype/value type 모순을 null/검토 사유로 보존한다. 최소형 메타 생략은 유지한다.
- 같은 조건 재실행: 06:57:22 UTC 완료. 수치/거짓 숫자 사실의 fit 승인은10/10→0/10,
  null 사실의 실행10/10은 관측1/min15/max15·상수 비활성으로 성공했다. 오류율 차이는
  -100%p이며 성능·자연 발생률·품질 개선은 아니다.
- 실제 기존11상품군·5fit/6transform의 전체 보고서 bytes·fingerprint와 모든 authority/hash는
  변경 전후·이전 저장 결과에서 동일했다. [원값/집계·한계](../measurements/2026-11-02-source-quantity-fit-integrity.md)를 보존했다.
- 관련 단위/실제 CLI 회귀235개와 변경 Python 파일의 Ruff/format 검사는 통과했다.
- 전체 `./scripts/check.sh` 통과: Python3.12/uv locked·repo guard·Ruff/format·pytest693개,
  B0/B1 고정 시나리오, 새 sdist/wheel과 runtime-only `python -I`의 실제 CLI/HTTP를 확인했다.
  새 패키지에서도 별도 손상4조건의 실제 offline receipt→수량 사실 거절/null 사실 fit을 확인했다.
  기존 health/B0/B1/exploration/similar/OpenAPI·production10초 수신 오류 계약도 보존했다.
  최초 sandbox 실행은 pytest 이후 fresh-build 의존성의 PyPI DNS 제한으로 실패했고 기록을
  보존했다. 필요한 네트워크/본인 동적 loopback 권한의 같은 전체 검사는 exit0·배포 보고서
  `passed/complete`로 완료했다. 기존 warning1개 외 검증 실패는 없으며 실패를 재분류해 숨기지 않았다.
- README: REC-CS05의 원천 완료 상태, REC-CS06의 HTTP decoder 의미 손실과 별개로
  명시 단위/수량 타입→숫자 변환→실제 scaler fit 오승인 경계를 재현·수정했다. 별도
  REC-CS07로 추가하고 기존 두 본문/순서를 byte 보존했다. 현재3/4·부족1이며 신규
  다중 서비스 카탈로그/독립 평가 또는 실제 연동 장애/fallback의 근거를 계속 확보한다.
- 최신 CI/Codex 리뷰·병합은 별도 게이트다. 최종 기한과 4시간 실행, `gpt-6.1-sol`/`max`,
  원본 보존·PR 정책을 유지하며 DAT02/AI03 전체를 완료로 승격하지 않는다.
