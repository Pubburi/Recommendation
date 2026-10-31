# DAT01/02 제한 수집·정제 파이프라인

- 기준 main `b1dca74`(#11), 작업 `codex/reviewed-entity-catalog`.
- 공식 CC0/접근/wbgetentities/etiquette와 P31/P176/P2665/P2234 필드를 확인했다. 주류 상품/상품군
  원천 확보를 진행했으나 새 검색 payload3개와 간격을 둔 단일 item GET이 모두 maxlag 보류였다.
  조회 불가와 실제 제품 부재를 구분하고 maxlag5를 완화·다른 endpoint로 우회하지 않는다.
- 단일 GET의 실제 HTTP200·501B·api_maxlag·acceptedfalse 영수증과 원문 hash를 ignored에 기록했다.
  신규 accepted0이며 카탈로그/검수SKU·실모델 학습 완료로 기록하지 않는다. Q1154088은 기존
  Wikipedia의 sitelink에서 발견한 후보이며 그 페이지의 본문·맛·이미지·수치를 학습하지 않았다.
- 초기에 payload.get(search,[])가 오류를 빈 결과처럼 표시할 위험을 확인하고 원문으로 정정했다.
  제품 수집기는 HTTP/JSON 외 APIerror/warning·success·정확ID/revision/shape를 통과해야만
  raw/projection을 기록한다. 오류 info/개인 경로는 진단에 포함하지 않는다.
- 최대10QID·고정 HTTPS/GET·maxlag5·식별UA·timeout/bytecap·redirect금지·새폴더/원자receipt 경계를
  구현했다. 소스 명세와 원문/정제/영수증 hash/revision을 보존하며 accepted가 학습 승인인 것은 아니다.
- 기존 CC0 4항목의 offline 재생은 같은 원문 해시·revision으로 성공했다. 이전 브랜드3/미확정1·
  SKU0 자료의 재생이며 신규 카탈로그 증가가 아니다. 실제 검색 maxlag payload도 offline 거절했다.
- 같은 fixture fit/legacy 감사만 반복하지 않고 실제 원천 보류의 잘못된 성공 상태를 차단하는
  필요 제품 코드를 완성했다. 원천이 정상일 때 개별 제품 단위/필드·권리를 검수한 카탈로그를
  계속 확보해야 하며 다른 독립 제품 작업을 원천 회복까지 대기시키지 않는다.
- README는 실제 외부계약/데이터오인 조건·영수증/ID/revision/불변snapshot 판단·실패 거절 근거가
  단순 health 초기설계보다 강하다고 판단해 그 사례 한 개를 교체한다. 기존 health 기능/기록과
  B0사례는 보존하고 총2/4를 유지한다. sourceaccepted0를 수집 성공/성능/추천 품질로 포장하지 않는다.
- CI는 자체 작은 payload만 재생하고 새 runtime-only wheel CLI의 성공/실패를 검증한다.
  실제 원문·카탈로그·영수증·요청 로그는 ignored에만 두며 aT 재시도/가입/키/외부문의/비용/AWS는 없다.
- 독립 검토의 깊은 JSON 진단 누락은 Python3.12에서20,000중첩/40KB대 입력으로 RecursionError·
  실제 CLI exit1/traceback·미완성 오류 receipt를 먼저 재현했다. 공통 parser가 고정 AuditError로
  변환해 catalog/collector CLI의 exit2·안전 진단·완성 실패 receipt와 원문/정제 미생성을 확인한다.
  공통 fix와 수집 feature를 독립 한국어 커밋으로 나눠 기존 이력을 보존한다.
- 최종 `check.sh`는 저장소/locked·Ruff·pytest256·B0계약8/8·B1fixture fit8/8, 새 sdist/wheel의
  runtime-only python-I 실제 source재생 성공/maxlag/깊은JSON 거절·legacy감사/B1 fit·실제
  health/B0/OpenAPI·중복ID422를 통과했다. 기존 TestClient 경고1건은 남아 있다. 마지막 README
  전체 코드 발췌/문서 정리 뒤 Ruff/저장소/차이 검사를 다시 통과했다. 성능 수치로 사용하지 않는다.
- 공통 파서 fix와 수집 기능은 서로 검토 가능한 한국어 커밋으로 나눈다. PR/최신리뷰/CI/병합은
  조정자가 처리하며 원천 보류를 구현 완료/서비스 카탈로그 확보로 바꾸지 않는다.
