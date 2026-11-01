# DAT02/04·AI03 — 다중 snapshot·미관측 제조사 cohort

- 기준 main `7418d436`, `codex/cross-producer-family-cohort`. Recommendation만 작성하며 root는
  PR/최신 CI·Codex·native/병합/main CI·브랜치/lease·공통 기획을 소유한다. DB·Backend/FE/
  공유 포트·성능 자원·새 원천 네트워크를 사용하지 않는다.
- 단일 raw/receipt 실험만 가능한 상태에서 기존 두 authority를 각각 검증해 실제11상품군/
  2제조사를 연결하는 CLI를 구현했다. 합성 수집 receipt를 만들지 않고 각 source/revision/
  receipt/review/manifest hash를 유지한다. `FamilyPartition`만 공통화해 기존 단일 입력 계약/
  TF-IDF·수치 fit·독립 평가기를 재사용한다. 서비스 API/랭커·SKU 승격은 바꾸지 않는다.
- source ID/선언 family group/선택revision 각각11, ID 중복/정규화label충돌0을 확인했다.
  strict P31/P176의 entity-valued·unqualified 관계를 사용하며 이름 추론이 아니다. 그룹은
  curator의 상품군 선언이라는 범위를 명시한다. 같은 ID를 양쪽에서 선택하면 자동 덮기/합치기
  대신 거절하고 그룹·제조사 관계가 fit/transform을 넘지 않게 한다.
- 17:45:04 UTC에 facts/그룹·5fit/6transform·query/gold/cutoff와 전체 spec hash를 첫 fit 전에
  동결했다. 새6개는 source 수량의 단위/포장 문맥 부족으로 unknown을 유지한다. 실제5×7/
  rank5·학습 도수5/용량0·변환 양쪽수량0관측을 기록했다. 미관측 producer6/6 OOV·text
  zero5/6/nonzero1/6과 positive1/zero-positive5의 분모/원순위를 함께 남긴다.
- 최종 같은 입력 두 보고서 전체·fingerprint/원 frozen hash를 재현했다. 이전 단일제조사
  실험과 데이터/분할이 달라 전후 품질/성능 비교로 합산하지 않는다. source class 사실 검색은
  사람 선호·서비스 품질·일반화/최종 평가가 아니다. 신규 업무매핑0/기존DEMO1을 유지한다.
- README 대표2/4/순서를 보존한다. 실제 두 제조사·미지원 범위/분모 근거는 늘었지만 물리 SKU/
  서비스 적합·사람의 관련성/최종 평가가 없고 사실 정답이 입력 class와 공유된다. 강한 독립
  서비스 문제 해결을 새로 확보했다고 보기 어려워 세 번째 사례로 숫자를 채우지 않는다.
- 다음은 허용 포장/변형과 업무 매핑·다른 주종/독립 관련성 확대다. 사용자/로그/외부 평가자를
  기다리거나 작은 카탈로그에 SVD를 강요하지 않는다. [관측 조건](../measurements/2026-11-02-cross-producer-cohort.md).

최종 회귀/배포 검증과 인계 상태를 아래에 기록한다.

- authored22개와 기존 family/평가36개 focused58개가 통과했다. 최초 fixture의 수집 출력이
  private 경계 밖이라 guard가 거절한 것은 private fixture 경로로 바로잡았으며 가드를 완화하지
  않았다. 실제 원천의 오류나 데이터 획득 실패로 보고하지 않는다.
- Python3.12.14 `./scripts/check.sh`: 안전 검사·locked 설치·Ruff/format·pytest522개·기존
  authored B0/B1 시나리오·새 sdist/wheel을 통과했다. runtime-only `python -I`의 별도
  snapshot cohort CLI·기존 source/export/fit CLI와 실제 health/B0/B1/OpenAPI·JSON 오류/
  본문 제한·프로덕션10초408도 성공했다. 기존 TestClient deprecation 경고1개는 남는다.
- PR 생성·최신 head CI/Codex·구체 미해결 지적/native 해결·병합/main CI·브랜치 정리는
  조정자가 담당하며 이 로컬 검증/모델 실행을 서비스 품질·전체 AI03 완료로 표시하지 않는다.
