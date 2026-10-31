# DAT01/02 — 원천 기본 라벨 정보 보존

- 기준 main `19e1dae`(#12), 작업 `codex/wikidata-default-labels`. Recommendation 단독 소유다.
- 공식 CC0/접근 etiquette를 재확인하고 기존 고정 GET/maxlag5·상한·timeout/프레이밍 검증 그대로
  복구를 한 번 확인했다. 정상1개, 이어서 공식 구조화 상품 링크의6개 후보를 소량 단일 GET으로
  확보했다. aT 보류 재시도·계정/키·외부문의·비용/AWS·이미지/외부 본문 요청은 없다.
- 실제6개 중3개 라벨이 null인데 공식 기본 라벨은 존재했다. `ko|en` 요청과 ko/en 선택이
  원인임을 확인하고 공식 mul API 근거로 `ko|en|mul`·ko→en→mul fallback·label_language를 구현했다.
  빈 라벨은 unknown, 설명·별칭·QID에서 이름을 추정하지 않는다. 기존 ko/en 우선순위를 보존한다.
- 자체 fixture의 수정 전9개 실패를 먼저 확인하고 수정했다. 작은 source 구조만 테스트하며 실제
  항목 수·이름·revision/원문은 unit 고정 정답이나 CI 입력으로 올리지 않는다.
- 실제 동일6QID·revision6/6·비라벨 필드6/6 비교에서 label 결측3/6→0/6(50%p감소), en3/mul3을
  확인했다. [원값·hash·조건·한계](../measurements/2026-11-01-default-labels.md)는 정보 보존 근거다.
  네트워크/모델/API 지연·실제 사용자 선호/추천 품질 개선으로 표현하지 않는다.
- 새 원문 해시에 명시 상품군5/브랜드1 검수 mapping을 작성하고 실제 audit CLI로 재생했다.
  이전 raw 해시의 mapping은 같은 revision이어도 고정 오류/종료2·출력 미생성으로 보류했다.
  기존 파일/영수증/검수는 덮어쓰지 않았다. 정규화 코드 버전의 별도 의미 검수도 필요하다.
- 실제 새 고유 source7개이며 전후 재조회6개를 새6상품으로 더하지 않는다. 포장/용량별 SKU0·
  B0내보내기0·실카탈로그 fit승격0, 용량/가격/그룹결측 각각6/6과 일반 percent 도수unknown1/6을
  보존했다. DAT01/02 전체, 실제 모델/품질/최종 평가·API/웹 통합 완료로 처리하지 않는다.
- CI의 새 runtime-only wheel은 authored mul-only payload의 실제 수집 CLI 재생과 source 언어를
  확인한다. 기존 health/B0/B1/원천 오류·deep JSON·HTTP framing 계약도 유지한다.
- README 두 사례는 유지한다. 실제 source 필드 유실 해결 근거는 있지만 기존 수집 신뢰성 사례와
  겹치고 서비스 SKU/특성 연결 효과는 아직 없어 숫자를 채우는 세 번째 사례로 나누지 않는다.
- 구현/로컬 검증 뒤 한국어 한 목적 fix 커밋으로 인계한다. PR·latest head 리뷰/필수 CI·병합/
  main CI/브랜치 정리·Notion·lease 해제는 조정자가 담당한다.
- 최종 `./scripts/check.sh`에서 저장소/locked·Ruff·pytest286·B0/B1각8/8·새 sdist/wheel의
  runtime-only python-I mul-only 실제 수집CLI 재생/원천언어·maxlag/deepJSON실패·legacy감사/B1fit·
  실제 health/B0/OpenAPI/중복ID422를 통과했다. 기존 TestClient 경고1건은 남았다.
  실제 작은 원천 표본의 정보 보존 결과와 이 자체 fixture 회귀/배포 검증은 구분한다.
