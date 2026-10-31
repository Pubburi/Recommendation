# DAT01/02 기존 시드·자산 실제 감사

- 기준 main `30fff1a`(#10), 작업 `codex/legacy-catalog-audit`.
- 이번은 같은 B1 fixture fit을 반복하는 작업이 아니라 기존 시드/이미지의 실제 데이터 준비 감사다.
  Recommendation만 수정하고 Backend/Frontend의 SQL·이미지·문서·웹 매핑은 읽기만 수행한다.
- 고정 Backend75b30c3 `data.sql`, Frontend a94346a의 pub자산/format 함수를 사용했다.
  SQL은 Git blob을 소유 임시 파일로 읽고 삭제했다. 사용자/암호 행은 보고서·별도 raw스냅샷에 없다.
  원문 해시·정렬된 자산 해시·범위/한계는 [실제 집계](../LEGACY-SEED-AUDIT.md)에 기록했다.
- 활성 INSERT8개/80행, 주종8개×10행, 각 시드 literal값80/80형태유효를 계산했다. 주석의 옛5행은
  제외했다. 독립 문장/행 계수와 실제 Frontend 함수의 매핑·일반 파일·SHA-256이 각각80/80 일치한다.
- 기존 PNG0/80과 현재 WebP80/80을 구분했다. exact/name/ref 중복0·동일바이트0그룹·미사용pub0이다.
  값/링크 존재를 사실·신선도·권리·SKU 검수로 바꾸지 않는다. 범위/집계가 다른 Wikidata4항목과 합산하지 않는다.
- 시드 가격/order_count를 시연 값으로 분리하고 상품 단위/개별 필드·용량/맛/향·이미지 허락 근거는
  미확인으로 격리했다. 현재 조사 범위의 미확인 상태이며 법적 권리 부재를 판정한 것이 아니다.
  실제 서비스 SKU·학습 승격0, B1 실카탈로그 fit·DAT01/02 전체 완료는 남아 있다.
- 제품 변경은 SQL을 실행하지 않는 strict literal extractor와 독립형 inventory/격리 CLI다.
  지원 불가 표현/변경문은 보류하고 지정 여섯 제품 필드만 추출한다. 경로·symlink·파일 크기·
  원본/변환 해시·Decimal 타입/문맥/underflow·새 출력 보존 경계를 검증한다. 추가 의존성은 없다.
- 원문80행·개별이미지해시·상품별격리출력·정확실행명령/비공개근거는 ignored에만 둔다.
  CI는 작은 자체fixture만 사용하며 실제80행을 고정 unit 정답으로 넣지 않는다.
- aT 보류 요청 재시도·다운로드·외부문의·계정/비용/AWS·타레포 변경·DB 실행은 없다.
- README는 실제 학습/분리 평가나 근거 해결 성과까지 확보하지 못했으므로 기존2/4와 순서를
  보존한다. 조사/인벤토리 집계를 성능 개선이나 새로운 사용자 장애 복구 사례로 꾸미지 않는다.
- 독립 검토에서 CTE/LOAD의 미지원 상품 변경문이 누락되고, 비제품 문자열 속 t_product가 과잉
  보류되는 세 경계를 재현했다. 문자열은 마스킹·backtick 식별자는 보존한 뒤 CTE 변경/LOAD를
  generic 오류로 보류하고 읽기 전용 CTE·비제품 변경/문자열은 통과시킨다. 실제80행 집계는 같다.
- 전체 `check.sh`는 저장소/locked·Ruff·pytest215, B0계약8/8·B1fixture fit8/8, 새 sdist/wheel의
  runtime-only python-I 실제 legacy감사 CLI·B1 fit·health/B0/OpenAPI·중복ID422를 통과했다.
  기존 Starlette/HTTPX TestClient 사용 중단 경고1건은 같다. 새59회귀는 작은 자체fixture이며
  실제80행의 사실 품질/권리나 시간 성능을 검증했다는 주장으로 바꾸지 않는다.
- PR/최신head 리뷰·CI·main 반영은 조정자 인계 이후 실제 상태를 확인한다.
