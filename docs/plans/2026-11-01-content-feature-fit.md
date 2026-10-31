# B1 오프라인 상품 표현 fit 증가분

- 기준 main `eb3fbeb`(#9), 작업 `codex/content-feature-fit`.
- 기존 B0/health HTTP를 보존하고 실행 가능한 실제 fit·transform·rank 모듈/CLI를 한 목적의
  증가분으로 구현한다. 사용자/로그/UI를 기다리지 않고 직접 만든 fixture로 검증하되 실SKU0·
  서비스 품질/AI03 전체 미완료를 유지한다.
- 공식 TF-IDF/MinMax/누수 방지 문서·PyPI의 배포/라이선스/런타임 요구사항을 확인하고
  scikit-learn1.9.1·NumPy2.5.4와 전이 의존성을 uv.lock에 고정했다. 학습/다운로드는 서버
  시작에 연결하지 않았고 모델 파일을 저장하지 않는다.
- 태그의 한국어 한 글자·띄어쓰기·taste/aroma namespace를 보존한다. 도수/용량의 관측값만
  학습하며 unknown·상수열을 임의 0/거리로 바꾸지 않는다. 활성 성분의 같은 비중·실제 양의
  기여와 OOV 개수를 설명한다. 초기 비중은 선호로 튜닝한 값이 아니다.
- 필수 조건 뒤 점수·동점 ID순·limit을 적용하고 선택 상품 자체/제외를 보존한다. 빈 취향·OOV·
  전체 zero-vector는 결정적 B0 대체, 빈 후보는 별도 사유다. Backend 지연/장애 대체와 구분한다.
- fixture11상품은 학습4/3상품군·변환7/6상품군이다. 동일 SKU변형 그룹은 경계를 넘지 못하며
  수동 적격 목록·독립 조건 검사와 8계약 시나리오로 확인한다. fit 이후 새 어휘/수치가 학습을
  바꾸지 않는지 검증한다. 이 명세는 실제 신규상품/최종 holdout이나 관련성 정답이 아니다.
- B0/B1의 같은 조건 순서·실제 점수/기여는 로컬 보고서에 기록한다. 순서 차이를 품질 개선으로
  쓰지 않는다. 독립 관련성 라벨이 없어 Recall/NDCG 미산출, 실측 성능/오류 개선 주장 없음.
- CLI는 authored_model_fixture만 실행하고 ignored 새 출력만 쓴다. CI는 원문/응답/어휘/IDF
  없는 요약만 보관한다. 새로운 wheel은 runtime-only python -I에서 실제 CLI fit을 검증한다.
- 검수 서비스 SKU/권리·source-to-feature 매핑, 독립 관련성/최종 평가·충분한 실카탈로그의
  SVD 적합성 비교·모델 준비/HTTP·Backend/웹 연동은 미완료다. aT 보류 동작은 재시도하지 않았다.
- README 사례는 기존2/4와 순서를 유지한다. 새 모듈의 허구 회귀를 실제 평가/성능 사례로
  승격하지 않으며 강한 독립 서비스 사례가 확보될 때 재검토한다.
- 최종 `./scripts/check.sh`에서 저장소/locked·Ruff·pytest151, 기존 고정 B0 8/8과 실제
  B1 fit 계약8/8, 새 sdist/wheel runtime-only python -I CLI fit·실제 health/B0/OpenAPI·
  중복ID422를 통과했다. 별도 CLI 재실행 보고서도 같은 입력/학습fingerprint·점수로 재현했다.
  기존 Starlette/HTTPX TestClient 사용 중단 경고 1건은 남아 있다.
- 신규 회귀35개는 수동 IDF/수치 범위·실기여·한국어 원자 태그·학습 후 fit 금지·필수/제외·
  unknown/실제0·상품군 누수/명세 모순·출력 보존을 검증한다. 테스트 개수를 성능 개선으로 쓰지 않는다.
- 구현·로컬 검증 완료이며 PR/최신 head 리뷰·CI·main 반영은 조정자 인계 뒤 실제 상태를 따른다.
