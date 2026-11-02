# R03 기준 상품 유사 후보의 명시 제공자

기준 main `d7561dff`·작업 `codex/similar-product-provider`다. 최신 기획의 R03은 AI01/F03을
선행으로 하는 P1 상품 상세 유사 후보다. 기존 B1의 오프라인 `similar`는 구현돼 있지만 HTTP에
노출하지 않았다. 다중 장바구니/주문 맥락·F10/F11을 요구하는 R07보다 선행과 재사용 범위가
명확한 R03의 추천 소유 증분을 선택했다. 기존 API 결함이나 잘못된 비교 모델을 새로 만들지 않는다.

## 사전 고정과 기존 동작

구현 전2026-11-02 02:38:27.995414Z에 직접 작성한9상품·시연 가격·명시 그룹·기준ID·hard
조건/예상 불변식을 동결했다. spec SHA256은
`6ce69ecc826121f5543a0f3ef45c4b3b0d2170131d1e21f14ead0c41f406dcbe`다.
기준은10, 같은 그룹 변형11, 사실이 같은 별도 그룹20과 일부 특성만 확인된80을 둔다. 도수 초과30,
도수 unknown40, 조건상 가격 unknown50, 판매 불가60, 명시 제외70은 결과에 나오면 안 된다.
기대는20이 먼저인 양수 후보20/80·10/11 제외·hard/unknown 보존과 원래 B1 항목의 기여 보존이다.
기대 후보 사실을 생산 점수/필터 helper로 생성하지 않았다. 정확 점수를 독립 사람의 관련성 라벨로 쓰지 않는다.

기존 실제 Uvicorn은 새 path에404를 반환했다. 같은 catalog와 기준에서 읽은 명시 profile의 기존
content HTTP는 `[10,11,20,80]`이었다. 일반 취향 추천은 본인/동일 그룹 제외를 요구하지 않으므로
이는 정상 계약이며 결함·나쁜 성능 기준선이 아니다. 원래 전체 B1 요청/응답과 동결 입력·PID/포트는
ignored에만 보존하고 소유 baseline 서버를 종료했다. 새 source/업무 매핑·서비스 SKU는 만들지 않았다.

## 선택과 구현

- 새 [similar API](../SIMILAR-API.md)는 명시 catalog 안의 reference_product_id만 사용한다. 별도
  user profile·원천ID·URL로 기준 사실을 추정하지 않는다. 입력 duplicate ID와 타입/상한은 먼저 거절한다.
- 정상 기준의 요청 catalog를 기존 `fit`에 전달하고 reference의 검수 `sku_group` 전체를 후보에서
  제거한 뒤 기존 `similar`를 호출한다. 본인/변형 제거를 기존1000개 exclude ID에 더하지 않는다.
  나머지 후보 간 그룹당1개/다양성은 R08 정책과 구분하며 여기에 자동 추가하지 않는다.
- 기준의 soft 주종/관측 태그·수치는 기존 B1에 전달하고 가격·판매/필수/제외는 hard 조건으로 유지한다.
  양수만 반환하되 원래 score/reasons/contributions는 바꾸지 않는다. 더 많은 수를 채우기 위한0점/
  hard 실패/동일 기준 그룹 복구는 없다. 기준의 주종을 후보의 hard 주종으로 강제하지 않는다.
- 기준 부재/판매 불가는 fit/import 없이 빈 fallback이다. group 후보를 결정할 수 없어 계산하지 않은
  eligible_count와 excluded_reference_group_count는0이 아닌 null이다. 정상 기준에서 group/hard 뒤
  적격0·unknown/OOV·무공유 특성은 기존 사유와 빈 items로 구분한다. 사용자 취향을 학습한 것처럼
  보이지 않도록 profile_source=reference_product_facts를 명시한다.
- 기존512KiB/전체10초 본문 수신·JSON 중복 key/원래 malformed 우선순위를 새 path에도 적용한다.
  모델/어휘는 요청 지역이고 시작/스키마/health와 기준 부재/판매 불가에서 NumPy/sklearn을 로드하지 않는다.
  수신 기한은 CPU fit 취소/지연 성능 보장이 아니다. 기존 B0/B1/R08·health 계약은 바꾸지 않는다.

원래 `similar` 엔진과 경량 B1 응답을 재사용해 별도 점수 구현을 피했다. 무조건 B0 ID순을 유사
결과로 채우는 대안은 근거 부재를 숨기므로 채택하지 않았고, 기준과 같은 변형까지 허용하는 대안도
기준의 재노출을 피하려고 배제했다. 빈 fallback의 표시/현재 상품 링크·가격/판매 재확인은 소비자
Backend/상세 화면에서 연결해야 한다. 내부 제공자만으로 전체 R03이 완료되지는 않는다.

## 실제 실행·검증

동일9상품 명세·동적127 loopback·Python3.12.14의 새 실제 서버에서 새 HTTP200과 후보
`[20,80]`, group 제거2개·hard 적격2개를 확인했다. 같은 기존 content의 **전체 응답은 구현 전과
동일**했고 새 items 두 개는 이전 B1의 해당 원항목 전체·같은 모델 지문을 보존했다. 새 응답 반복도
전체 동일하며 기준999의 부재는 빈 items·미계산 null/무표현 fallback이었다. 응답을 합성하지 않았고
baseline/after 소유 PID 둘 다 종료했다. 이 관측은 허구 사실/새 계약의 동작이며 전후 서비스 오류율·
모델 선호 품질·속도 개선이나 기존 HTTP 장애 수정으로 표현하지 않는다.

Python3.12.14·고정 uv로 `./scripts/check.sh`가 성공했다. Ruff/format·pytest642개(새25개),
기존 동결 시나리오와 새 sdist/wheel이 통과했다. checkout 밖 runtime-only 환경의 `python -I`에서
실제 health/B0/B1/R08/similar/OpenAPI, ref ID boolean/duplicate raw JSON·media별 문법 오류와
512KiB/production10초 부분 본문408을 확인했다. 기존 TestClient deprecation 경고1개가 남는다.
패키징 helper의 성공은 서비스 카탈로그/사용자 품질 증거가 아니며 CI 시간·테스트 수를 앱 성능으로 쓰지 않는다.

단위/HTTP 회귀는 soft/hard 분리·unknown/실제0·reference 본인/그룹·원항목/기여·scarcity,
missing/unavailable 미계산·빈/상수 무정보·무공유 특성, 제외 ID 예산·입력 순열/동시 요청 격리와
엄격 타입·원문 오류 비반사·startup 미로딩을 확인한다. production 수신 기한은10초 그대로이며
ASGI 짧은 기한 회귀와 분모를 합쳐 서비스 지연 결과로 쓰지 않는다.

## 데이터·완료 상태와 README

이번 신규 외부 source GET0·실서비스 SKU/업무 mapping0·실서비스 카탈로그 fit0이다. 허구 요청은
실제로 fit했지만 기존 별도 source-backed DEMO1상품 fit·상품군11개/제조사2개·6상품군/11문맥
관측과 grain/분모를 합치지 않는다. 실제 사용자/독립 선호 라벨이 없어 Recall/NDCG를 새로 만들지
않으며, 이 부재를 전체 AI03의 차단 사유로 삼지 않는다. 허용 원천/판매SKU/고정 사실 평가는 별도 계속한다.

README 기존 두 사례의 원천 상태 오인·추천 JSON 의미 유실과 비교했다. 이번은 새 제공자의 설계와
기능 동작이며 실제 과거 결함/다중 서비스 카탈로그/사용자 관련성·웹 영향의 더 강한 독립 근거가
없어 두 본문/순서를 byte 보존하고 기능 행만 추가한다. 대표2/4·부족2를 유지한다.

현재 상태는 구현·로컬 검증 완료이며 최신 head 필수 CI/완료 Codex·미해결0·Squash/mainCI·
ff-only/병합 브랜치 삭제는 조정자의 별도 게이트다. 전체 R03 Backend/상세 화면·유효 링크,
R07 장바구니/주문 맥락·실서비스 카탈로그 품질·최종 평가/기타 필수 기능은 미완료다.
