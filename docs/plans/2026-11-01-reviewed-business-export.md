# DAT02/C03 — 업무 스냅샷과 명시 시연 매핑

- 기준 main `4d972b1`, 작업 `codex/reviewed-business-export`. Recommendation은 소비 gate/
  데이터·모델·시험/문서를 소유하고 root는 제공자 통합 환경·기획·PR/최신 리뷰·CI/병합/main CI·
  브랜치 정리·lease를 담당한다. root 수집 snapshot은 읽기만 하며 다른 레포/DB를 수정하지 않는다.
- 제공자 ProductResponse7/Features8·ApiResponse 실제 코드를 읽어 계약을 정했다. 새 API/
  GTIN 저장·서버 revision을 추가하지 않는다. 이름/QID/순서 대신 source catalog·snapshot
  파일/전체 응답 content hash·명시 ID/그룹·일치하는 수량과 UTC 검수 시각에 결속한다.
- source_catalog의 같은 검증을 load 함수로 재사용해 생성 파일을 단독 신뢰하지 않는다.
  원문 권리/ID/revision·분류/hold를 보존한다. source/업무 모순·미확인 수량·중복/타입/범위·
  변경 응답·origin 혼합은 거절한다. wire에는 ID/업무 주종·시연 가격·일치 수량/그룹만 쓰며
  source unknown 맛/향은 null로 보존하고 설명/이미지·태그/주문 수/URL을 넣지 않는다.
- 캡처0–60초·미래 금지·export5분과 캡처 후 review를 요구한다. 이것은 로컬 정책이지
  원자 읽기/서버 revision·실시간 판매/재고 보장이 아니다. available은 명시된 공개 탐색 목적
  행 존재와 시연 선택이며 소비 Backend는 현재 행/가격/필수 조건을 다시 확인한다.
- root가 전용 업무 API로 만든 허구 DEMO상품1개를 실제 읽은 owned_demo_fixture를 받아
  5분 내 명시 mapping·CLI export에 성공했다. 그 파일을 Recommendation 자신의 동적
  포트에 보내 B0/B1 HTTP200·같은 반환 ID/적격1개를 확인했다. 공유8000/다른 DB에 접근하지
  않았고 본인 프로세스만 정리했다. 이 허구 상품을 실제 주류/사용자 품질로 쓰지 않는다.
- 실제 CC0 원천4/검수 후보1과 기존 업무80 snapshot은 별도 무매핑/요청파일0이다.
  새 source GET·aT 거절 재시도/우회·외부 문의/키·유료/AWS·모바일·PG 작업은 없다.
- 첫 HTTP harness가 venv symlink를 resolve해 base Python으로 실행하면서 uvicorn 모듈
  없음으로 실패했다. venv 경로를 보존해 수정하고 실제 HTTP를 통과했다. 제품 장애나 성능
  개선으로 표시하지 않는다. 원문 개인 경로·로컬 로그는 공개하지 않는다.
- 회귀는 ID/원응답/참조/그룹/수량·unknown·origin·freshness/UTC·파일 변경·완성 receipt와
  원문 비노출을 확인한다. CI는 authored snapshot만 사용하며 runtime-only 새 wheel의 CLI가
  만든 exact export 파일을 기존 B0/B1 HTTP에 보낸다. root의 실제 업무 API 통합과 구분한다.
- README2/4·순서를 보존한다. 매핑/버전/상태 경계의 구현은 확보했지만 데이터 정본/평가
  후보 소재와 겹치며 실제 허용 상품 매핑/추천 품질의 독립 결과는 아직 없다. 같은 pipeline을
  나눠 수를 채우지 않는다. 서비스 SKU·fit/관련성·전체 DAT/AI03/20기능 완료와 구분한다.

최종 검증과 인계는 아래에 기록한다. 성능 과제가 아니며 가상 지연 감소율이나 테스트 횟수를
앱 최적화 성과로 쓰지 않는다. 정본은 [BUSINESS-EXPORT](../BUSINESS-EXPORT.md)다.

## 최종 검증·인계

- `check.sh`의 저장소/locked·Ruff·pytest442·기존 B0/B1 각각8/8, 새 sdist/wheel의
  runtime-only 기존/새 export CLI·그 exact 파일의 실제 B0/B1 HTTP·health/OpenAPI와
  production10초 부분본문408을 통과했다. 기존 TestClient deprecation1건은 남아 있다.
  authored CI와 root의 실제 전용 업무 API snapshot→owned DEMO 계약 검증을 구분한다.
- 실제 공개 원천 후보1/기존 업무80의 무매핑·요청파일0과 별도 허구 DEMO1개 계약만 완료했다.
  실서비스 SKU·실매핑·실카탈로그 fit/관련성/최종 평가는 미완료다. source 원문/curation/
  snapshot/매핑·검증 응답/로그는 ignored에만 보관한다. API-origin/자격정보를 wire에 넣지 않았다.
- root의 읽기 전용 검토에 추가 구체 결함은 없었다. 커밋/push 뒤 최신 head의 Codex/필수 CI·
  미해결 지적 없음·PR 병합/main CI는 root 최종 게이트다. 앞 head 결과로 대체하지 않는다.

## 다음 실제 카탈로그·학습 우선순위

1. 이미 검수한 공개 source-container를 별도 합의한 폐기 전용 업무 카탈로그에 연결한다.
   허용 사실·명시 시연 가격·자체 placeholder 이미지·출처 범위를 제공자/root와 맞추고,
   실제 반환 ID·snapshot과 명시 매핑을 검증한다. 기존 사용자 DB를 수정하지 않으며 실제
   공개 사실과 허구 fixture origin을 혼합하지 않는다. 이번 PR에서 업무 publish를 하지 않는다.
2. 새 gate 반복 확장 대신 허용 CC0의 명시 용기/용량/도수가 있는 개별 제품을 최대10ID의
   공식 소량 조회로 확대하고, 독립 식별/원천 단위·변형 그룹과 unknown을 검수한다. source
   부족을 사용자·미래 로그·평가자 부재의 차단으로 바꾸지 않고 허용 대안/직접 검수를 진행한다.
3. 튜닝 전에 상품 사실·필수/제외 시나리오를 고정하고 실제 검수 카탈로그의 known-catalog
   B1 fit과 B0 비교로 진입한다. 단일 상품/상수 수치의 정보 부족과 다중 그룹 전의 일반화
   미완료를 보고한다. 새로운 상품 일반화는 그룹 분리/fit-only 전처리로 따로 검증하며,
   독립 관련성 라벨이 없으면 Recall/NDCG를 만들지 않는다. 작은 자료에 SVD를 강요하지 않는다.
