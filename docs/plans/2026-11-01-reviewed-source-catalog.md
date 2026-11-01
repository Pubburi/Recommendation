# DAT01/02/03 — 수동 scope의 원천 포장 카탈로그

- 기준 main `6efaa4b`, 작업 `codex/reviewed-source-catalog`. Recommendation은 데이터/모델
  상세·코드/테스트/기록을 소유하고 root는 기획·공통 연동·PR/최신 리뷰·CI/병합/main CI와
  브랜치 정리·lease를 담당한다. 같은 기존 package 감사/5개 family fit의 재실행만으로
  진척을 대신하지 않고 포장 grain 검수에서 실제 원천 카탈로그로 이어지는 다음 단위를 완성한다.
- H10의 포장 후보1개는 CC0 원천에 can·GTIN·mL·vol%가 함께 있으나 P31에 brand도 섞였다.
  독립 공식 소매자 자신의 상품 페이지에서 같은 GTIN/500mL/can/5vol%를 확인해 이번에는
  한 용기의 표현만 수동 선택한다. 외부 페이지는 식별 교차검수 메모·URL이고 데이터 필드의
  정본은 이미 허용된 raw/revision/hash다. 상품 묶음수·제조사·맛/향/가격을 추정하지 않는다.
- Manitoba 약관의 as-is/copyright를 공개 데이터셋 승인으로 바꾸지 않는다. Royal Swinkels
  공식 portfolio는5% 제품군 확인뿐이며 복사 제한에 따라 본문/이미지를 데이터로 보관하지 않는다.
  페이지를 권리/식별 확인을 위해 읽었으며 외부 원문/이미지·상품 설명/리뷰를 데이터 파일이나
  모델 입력으로 보관하지 않았다. aT 특정 거절
  우회/재시도·OFF 폼·계정/키/유료·외부 문의·AWS·DB 변경도 없다.
- 새 `source_catalog`의 수동 명세는 raw/receipt/manifest 파일 hash·버전/UTC 시각과 별도
  사실 기대값·식별 scope·문자열 ID/변형 그룹을 고정한다. 기존 accepted receipt gate와 전체
  package 감사를 재사용하고 shared ID/unknown/문맥·미지정/중복·변경 입력은 보류한다.
  brand/container 혼합만 한정 해석을 별도로 기록하며 원래 분류/hold는 그대로 보존한다.
- 실제4항목의 같은 원문에서1개 후보·1개 수동 그룹을 선택했고 나머지3개는 카탈로그에 넣지
  않았다. source record는 업무 SKU/Backend ID가 아니다. 실제 업무 snapshot·명시 매핑이
  없어 wire export/매핑/서비스 fit승격0을 유지한다. 기존 H10의4/4 수동 보류와 sourcecatalog
  1개 한정 검수를 같은 상태 숫자로 합산하지 않는다. 개별 데이터·명세/출력은 ignored다.
- 각 feature의 정본/라이선스·property/단위와 source ID/revision/raw hash, 수동 선택의
  spec hash를 보존한다. 실제 권리 확인과 식별 검수·업무 매핑·서비스 학습/관련성 평가는
  서로 다른 완료 조건이다. URL 형식/사실 일치는 권위나 실제 권리를 프로그램이 인증한 것이 아니다.
- [검수 계약](../SOURCE-CATALOG.md)에 따라 intended grain을 source-container로
  고정하고 원천4/선택1/미선택3·관측값/unknown·기존 충돌/수동 해석·매핑 부재를 점검한다.
  외부 사용자·로그/평가자·미래 이벤트를 기다리지 않고 독립 고정 사실 명세를 직접 실행한다.
  모델을 학습하거나 단일 후보로 추천 순위/Recall/NDCG·사용자 만족도를 평가했다고 하지 않는다.
- 자체 회귀는 frozen 사실/field provenance·원래 분류/hold 보존·source파일/검수 변경·미지정/
  중복 ID·외부 HTTPS 검수 링크/UTC·미선택 item의 qualified GTIN 충돌·실제 CLI/부분 쓰기
  실패의 receipt·기존 결과 보존을 확인한다. 새 wheel은 자체 snapshot offline 수집→새 CLI
  curation을 runtime-only `python -I`에서 실행하며 CI에 실제 원천/카탈로그를 전달하지 않는다.
- README 현재2/4와 순서를 보존한다. 실제 포장 grain/식별과 명세 결속은 늘었지만 현재
  수집 신뢰성 사례와 후보 데이터 경계 소재에 겹치고 독립 서비스 영향/추천 결과까지 확보하지
  않았다. 새로운 사례 수를 채우기 위해 쪼개지 않으며 부족한2개는 미완료로 관리한다.

최종 검증·미완료/PR 상태는 실행 후 아래에 기록한다. 성능 과제가 아니므로 지연/최적화 수치를
생성하지 않는다. 서비스 SKU/명시 매핑·실서비스 데이터 fit/품질·전체 DAT 완료와 구분한다.

## 실제 실행·검증과 인계

- 실제4항목의 같은 raw/receipt와 고정 curation을 새 디렉터리 두 곳에서 실행했다.
  source-catalog/curation-report/receipt3파일이 byte-identical임을 확인했다. 추가 원천 GET0,
  원천4/선택1/미선택3·그룹1·원래 혼합 보류 보존·Backend ID/매핑·wire/서비스 fit0이다.
  이 재생은 신규 수집·모델 fit이나 독립 관련성 평가가 아니다. raw/receipt/curation/출력 해시와
  실제 메모·재생 대조는 ignored에 보존한다.
- 최종 `check.sh`는 저장소/locked·Ruff·pytest416·기존 B0/B1 각각8/8·새 sdist/wheel의
  runtime-only 기존/신규 CLI·자체 source-container curation·실제 health/B0/B1/OpenAPI·
  production10초 부분본문408을 통과했다. 기존 TestClient deprecation1건은 남아 있다.
  실제 데이터/외부 검수 URL·공유 DB/8000을 CI에서 사용하지 않는다.
- 테스트 준비 단계에서 다중 item fixture를 단일 ID로 collector에 전달해 정확 ID gate가
  거절한 실패가 있었다. 요청 ID를 fixture의 실제 item 집합으로 맞춰 준비 코드를 수정했다.
  제품 오류나 실제 원천 데이터 개선으로 표시하지 않는다.
- 구현·로컬 검증까지 완료했다. 최신 head의 필수 CI·Codex 리뷰·미해결 지적 없음과 PR
  병합/main CI는 조정자의 최종 게이트가 필요하다. 실제 업무 snapshot/명시 매핑·서비스
  카탈로그의 범위 확장/완전한 변형 감사·서비스 B1 fit/독립 관련성 평가는 미완료다.
