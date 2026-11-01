# AI02/C03 — B1 요청 카탈로그 HTTP 연결

- 기준 main `5afc477`, 작업 `codex/content-http-contract`, Recommendation 단독 소유다.
- `POST /v1/recommendations/content`의 catalog/profile/constraints/limit과 기존 B1 응답에
  fit_scope=request_catalog·representation_fitted·nullable model_fingerprint를 합의했다.
- adapter는 기존 FittedContentModel을 요청마다 지역 변수로 생성해 전체 명시 catalog를 fit/rank한다.
  중복 랭커·전역 cache/사용자 상태·입력/모델 저장·시작/health/B0 fit·외부 데이터/API 의존은 없다.
- representation_fitted는 실제 vocabulary 또는 활성 관측 수치 범위가 있을 때만 true다. 빈 catalog는
  fit하지 않고, nonempty 무정보/상수만 있으면 false/null로 기본순 반환한다. 단계 실행을 품질이나
  사용 가능한 표현으로 표시하지 않는다. 기존 offline ContentResponse 계약은 유지한다.
- soft 취향과 hard/제외·unknown/실제0·실기여/점수 합·OOV/세 fallback·순열/동시·이전 요청과
  모델 상태 분리·엄격 유형/상한·원문 비노출을 직접 쓴 HTTP fixture로 검증한다.
- 두 POST의512KiB 원문 제한을 보존하고 전체 수신10초/고정408을 적용한다. 무응답/드립·chunk누적·
  끊긴 연결이 parser/fit에 진입하지 않는 ASGI 검증과 실제 Uvicorn 부분본문408을 연결한다.
  취소되지 않는 CPU thread를 중단 완료로 기록하는 timeout은 도입하지 않는다.
- known-catalog representation이며 상품군 분리 일반화/사용자 선호 학습이 아니다. 제공자의
  권리/식별 검수 책임을 consent flag로 대체하지 않는다. legacy80/원본/이미지·실서비스 SKU를
  이번에 fit하지 않으며 HTTP fixture 연결을 서비스 데이터 fit·품질 완료로 승격하지 않는다.
- sourcefamily5의3fit/2transform 실험·주종 OOV2/2·서비스SKU0와 데이터/평가 한계는 유지한다.
  Backend는 기존 B0/default 연동을 독립 진행하며 B1을 선행 조건으로 기다리지 않는다.
- README 기존2/4·순서는 보존한다. 새 HTTP·상태 격리의 예방적 설계/연결은 확보했지만 실제
  서비스 장애/품질·독립 평가 없이 새로운 대표 사례를 강제로 채우지 않는다.
- 계약 정본은 [CONTENT-API](../CONTENT-API.md), 서비스 B1 엔진은 기존 CONTENT-MODEL이다.
  한국어 한 목적 feat 커밋·PR 초안/검증 뒤 root에 인계한다. 최신 리뷰/CI·PR/병합/mainCI·
  브랜치 정리·Notion·lease 해제는 root 소유다.
- 첫 전체 검증은 pytest346·기존 B0/B1각8/8 뒤 격리 main import10초에서 실패했다. 새 HTTP
  스키마가 content_model을 통해 수치 라이브러리를 시작 시 불러온 것이 원인이었다. 한계를
  늘리지 않고 경량 content_contracts로 동일 계약을 분리·기존 offline import 경로 재노출·
  nonempty B1 요청에서만 엔진 로딩으로 수정했다. 새 프로세스와 wheel에서 main/OpenAPI의
  NumPy/sklearn 미로드를 검증하고 첫 B1 HTTP 클라이언트만 별도30초 한계로 검사한다.
  이 검증 실패/수정은 서비스 성능 개선 수치나 과거 운영 장애 복구로 포장하지 않는다.
- 최종 `check.sh`는 저장소/locked·Ruff·pytest347(새HTTP36회귀)·기존 B0/B1각8/8·새 sdist/wheel의
  runtime-only 기존 CLI/상품군 fit·실제 health/B0/B1/기여·제약/빈/OOV/무정보/요청격리·422/413·
  실제10초 부분 HTTP 본문408/OpenAPI를 통과했다. 기존 TestClient 경고1건은 남아 있다.
  fresh main/OpenAPI의 수치 라이브러리 미로드와 기존10초 import 검사도 통과했다.

## PR15 후속 — B0 후보 적격성의 호출 범위

- Backend 기본 목록은 현재 행 존재만 확인하며 판매/재고 필드나 판매 검증을 제공하지 않는다.
  B0 정본의 available을 호출자가 확인한 목적별 후보 적격성으로 설명하고 공개 목록 노출과
  판매/재고 적격성을 구분했다. 해당 Backend 계약을 연결하되 unknown→true의 일반 허용이나
  판매/주문 조건 완화를 승인하지 않는다.
- 변경은 B0 문서·이 계획에 한정한다. 필드/알고리즘·앱/테스트/모델/기존 B1과 legacy80 fit
  경계는 변경하지 않았다. 문서 차이/저장소 검사를 확인하고 별도 한국어 docs 커밋으로 남긴다.
  조정자가 새 head의 필수 CI·Codex 리뷰를 다시 확인하며 앞 head 성공을 재사용하지 않는다.
