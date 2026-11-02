# 원천 수량 의미가 실제 fit에 들어가는 경계

## 조건과 사전 기대

- 기준 `38b32b8`, Python3.12.14·locked scikit-learn1.9.1, 로컬 동일 환경·같은 상품군 분할이다.
  외부 원천 GET·DB·공유 서버·성능 부하는 사용하지 않았다.
- 구현 전 2026-11-02 06:54:00 UTC에 ignored 명세의 입력 조건·독립 기대·authority 해시를
  고정했다. 명세 SHA-256은 `bc00f3fb04c283185398ca186768a228d1cb8612ffd30b2a7ef960bb904b1d99`다.
- 직접 작성한 Q1/Q2/Q3 세 상품군 중 Q1/Q2는 fit, Q3는 transform이다. 원래 도수는
  5/15/25이며 Q1 수량 statement 하나만 매 실행 손상시킨다. 단위 7조건과 명시 메타데이터
  3조건은 [안전한 입력별 원값/집계](2026-11-02-source-quantity-fit-integrity.json)에 남겼다.
- 동결 기대는 지원 URI/수량 타입·property가 모순이면 Q1 도수가 null이라는 것이다. 숫자5로
  선언한 사실은 fit 전에 거절하고, null 사실에서는 Q2의15만 관측해 상수 열을 비활성화해야 한다.
  모델 결과를 기대값 생성에 사용하지 않았다.

## 실제 전후 실행

각 입력을 실제 `wikidata_collect --snapshot` CLI로 offline 재생하고 새 accepted receipt·
원문/review/manifest/receipt hash를 결속했다. 같은 `source_family_experiment` CLI에
숫자 사실 명세를 보내 발행 결과를 확인한 뒤, 수정 후에는 Q1 사실만 null로 선언한 별도 명세로
성공 경계도 확인했다. 원문·receipt·명령/진단·모델 보고서·harness는 ignored에만 보존했다.

| 고정 손상 표본에서의 결과 | 변경 전 | 변경 후 |
|---|---:|---:|
| 잘못된 수량을 숫자5로 정규화 | 10/10 | 0/10 |
| 숫자5 사실의 실제 fit/report 승인 | 10/10 | 0/10 |
| 같은 원문에서 null 사실 명세로 성공 | 변경 후 조건 | 10/10 |

첫 두 항목의 오류율은 100%→0%, 차이는 **-100%p**다. 이는 사전 고정한 손상 입력의 정확성
결과이며 자연 발생률·전체 데이터 품질·추천 만족도·지연 개선이 아니다. 전 실행은 실제 numeric
fit 관측2/min5/max15/활성, 수정 후 null 사실의 실행은 관측1/min15/max15/상수 비활성이다.
0을 채운 값이나 원천 truth가 없는데 추가한 관측은 없다. 잘못된 숫자 사실은 exit2의
`manual_facts_conflict_with_reviewed_source`로 보고서 발행 전에 거절됐다.

기존 최소형 메타데이터·명시 정상 메타데이터와 HTTP/HTTPS의 volume-percent/mL/L/cL,
0도수·양수 용량·문맥/범위/다중값·deprecated 정책도 유지했다. 같은 URI 변환표를 scalar·
package·volume-context 경로가 공유하되 포장/문맥의 더 엄격한 명시 shape 조건은 유지한다.

## 실제 원천 결과의 보존과 한계

실제 원문을 손상시키지 않았다. 기존 검수11상품군/2snapshot·5fit/6transform의 원래 동결
명세를 변경 전후 각각 실행했으며, 전체 보고서 bytes는 이전 저장 보고서와도 동일했다.

- 전체 보고서 SHA-256: `dcdea43cca59628cd6c3041db2f00393bf1e1ca0c3f5be781f529ae6adad73e2`
- fit fingerprint: `0b1dea7937e89b8bf3cbe5180ec2ea8a6a9fbe467725a5e9340021bde0853748`
- 기존 raw/accepted receipt/review·원천 manifest·동결 명세 해시는 불변이다.

이것은 기존 source-family 실험의 재실행이며 신규 수집·서비스 SKU 매핑·서비스 카탈로그
학습이나 AI03 전체 완료가 아니다. 실제 원천이 오염됐다는 관측도 아니다. URI 허용 목록은
현재 지원 단위의 식별 정책이고 외부 문서 진실성·권리·물리 SKU 정체성을 인증하지 않는다.

## 재현과 대안

```bash
uv run --locked pytest -q tests/test_catalog_audit.py tests/test_source_family_experiment.py \
  tests/test_package_identity_audit.py tests/test_volume_context.py
./scripts/check.sh
```

회귀는 독립 authored 입력과 새 receipt/hash로 CLI 거절·null 사실의 fit을 재현한다.
전체 검사는 새 sdist/wheel을 runtime-only 환경에 설치한 `python -I`의 같은 실제 CLI·기존 HTTP를
검증한다. 원천/모델 파라미터는 공개하지 않는다.

접미사 추정은 구현이 짧지만 다른 호스트의 ID를 동일 단위로 승인한다. 모든 레코드를 통째로
거절하면 정상 라벨·주종·생산자까지 잃고, 최소형 메타 생략까지 강제하면 기존 지원 입력을
불필요하게 거절한다. 따라서 수량만 unknown으로 남겨 검토 사유를 붙이고 기존 fit의 사실 대조로
거짓 숫자 선언을 막았다. 지원 원천/단위를 넓힐 때는 명시 URI 변환표와 사실 검수를 확장해야 한다.
