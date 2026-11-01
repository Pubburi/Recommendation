# DAT01/03/04 — 새 원천 상품군과 고정 사실 검색 평가

- 기준 `378de7f`, `codex/source-family-fact-evaluation`. Recommendation만 작성하고 root가
  기획/최종 PR·리뷰/CI/병합/main CI/브랜치·lease를 소유한다. 별도 업무 DB/서버는 요청하지 않았다.
- 같은1상품 fit/게이트 반복 대신 실제 다른6개 명시 상품군과4fit/2transform·사전 고정 exact-P31
  관련성·독립 지표 검사기를 추가했다. 기존 TF-IDF를 재사용하며 서비스 API/랭커/모델은 바꾸지 않는다.
- 발견 GET은 로컬 harness의 반환 처리 오류 후 명시 재실행을 포함한 총2회다. 첫 HTTP200은
  결과 미확정·두 번째1043B/8ID, strict collector1GET/112755B/8accepted였다. 이전 원문과
  대조해 기존1·신규7이고6개 상품군 선택/다른1개 브랜드 보류다. 원천 차단·maxlag 임계 우회나
  자동 retry는 없었다. 별도 제조사 페이지429 뒤 추가 조회도 중단했다.
- 공식 P2665 단위와 다른 generic percent·포장 qualifier 용량은 unknown 유지다. 외부 본문/
  맛/가격/이미지 수집·추정·단위 변경을 하지 않았다. 소스 상품군과 판매 SKU·업무 ID는 구분한다.
- fit 전에 명세/hash/시각·사실·6그룹/4fit2transform·두 질의/후보/정답/cutoff를 고정했다.
  같은 스타일의 서로 다른2그룹 중1개는 변환에 두었다. 비교 참고순은 기존 source ID 문자열
  정렬이며 Backend의 숫자 ID B0와 별개다. 불리한 기준선을 사후 선택해 개선율을 만들지 않는다.
- 독립 검사기는 생산용 fit/순위 없이 전체 후보/순서·score를 검사한 뒤 수동 사실 정답으로
  이진 Recall/NDCG를 계산한다. 동일 P31을 입력 특성과 사실 정답으로 쓰므로 사람 선호/
  독립 의미 유사도 평가가 아니다. positive1질의/후보4에서 원순위와 지표를 남기고 positive0
  질의1은 지표 생략·macro 분모 제외 사유/원순위를 보존했다.
- 실제4×5/rank4, 스타일4+공통 제조사1어휘와 수치0관측/all_unknown을 확인했다. 한 변환은
  클래스/제조사 지원, 다른 변환은 클래스 OOV/공통 제조사만 남았다. 동일 입력의 전체 보고서/
  fingerprint와 frozen hash를 재현했다. [관측/한계](../measurements/2026-11-01-source-family-fact-evaluation.md).
- 새 서비스 매핑0이다. 기존 별도 source-backed 업무 DEMO1 fit 기록은 보존한다. 실제6상품군
  실험·tiny 사실 관련성을 신규 SKU/실서비스 품질·일반화/AI03 전체 완료로 올리지 않는다.
- README 기존2/4/순서를 보존한다. 새 실제 상품군·독립 분모/분리·OOV 근거는 강화됐지만
  같은 제조사/양성1질의·입력 P31과 공유하는 사실 정답이라 독립 서비스/선호 품질 사례로
  기존 두 실문제 해결보다 강하다고 보기 어렵다. 부족한 두 사례를 수집/fit 횟수로 채우지 않는다.

최종 회귀·runtime-only 패키지·커밋/PR 인계 상태는 아래에 기록한다.

- Python3.12.14 `./scripts/check.sh` 전체 성공: 저장소 안전 검사·locked 설치·Ruff/format·
  pytest464개와 기존 authored B0/B1 계약, 새 sdist/wheel의 runtime-only `python -I`를 확인했다.
  원천 상품군 CLI의 실제 fit/transform·무양성 사실 질의와 별도 양성 지표 계산, 기존 export/
  reviewed fit·실제 HTTP health/B0/B1/OpenAPI·본문 크기/기한 회귀를 통과했다.
  Starlette TestClient의 기존 deprecation 경고1개는 남는다. CI 실패를 숨기는 설정은 바꾸지 않았다.
- 조정자의 읽기 전용 정적 검토에서 추가 구체 결함은 없었다. 커밋/푸시 후 최신 head의 필수
  CI·Codex/미해결 지적·병합/main CI 확인은 조정자에게 인계하며 로컬 통과를 병합으로 표시하지 않는다.
