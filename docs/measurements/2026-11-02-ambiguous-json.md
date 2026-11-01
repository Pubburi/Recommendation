# 모호한 추천 JSON의 수정 전후 정확성 관측

2026-11-02 한국 시간, 기준 main `bcb1b1d`, Python3.12.14의 같은 로컬 checkout·동결 허구 입력/
harness로 직접 Uvicorn HTTP를 비교했다. OS가 예약한 독립 loopback 포트를 자식 서버에 넘기고
각 실행의 서버 PID·shutdown/finished 로그와 종료를 확인했다. DB·공유8000·외부 원천/이미지는
사용하지 않았고 실제 사용자 트래픽/서비스 지연을 측정한 것이 아니다.

## 조건과 원인

- 두 endpoint 각각 도수 상한을5/50으로 중복한 요청과 상품 ID를1/2로 중복한 요청을 보냈다.
  상품/ID·시연 수치는 직접 만든 오류 재현 자료이며 실제 주류나 서비스 사고 이력이 아니다.
- 수정 전 decoder가 같은 key의 마지막 값만 남겨 typed validation에 전달했다. 필터 자체는
  이미 바뀐 상한50을 정확히 적용했으므로40도 상품을 반환했고 상품 ID도2로 바뀌었다.
  첫 값5가 정답이라고 선택하는 대신 전체 모호한 요청을 거절하는 것이 수정 목표다.
- 같은 harness SHA `40ccd37557e43c9e4876a90d5eec24afe1fcca2950de1fd3002ca4ff3d1cadd2`와
  입력 SHA `f533c43007d6c0f23eb06472b55d1196d67f3fc7e9627d6999523e0f4127304b`를 전후 유지했다.
  원응답/개별 결과·PID/log는 ignored에만 보관한다.

| 동결 재현 조건 | 수정 전 | 수정 후 |
|---|---|---|
| B0 중복 도수 상한 | HTTP200·40도 상품 반환 | HTTP422·duplicate_json_key |
| B1 중복 도수 상한 | HTTP200·40도 상품 반환 | HTTP422·duplicate_json_key |
| B0 중복 상품 ID | HTTP200·마지막 ID2 반환 | HTTP422·duplicate_json_key |
| B1 중복 상품 ID | HTTP200·마지막 ID2 반환 | HTTP422·duplicate_json_key |
| 정상 상한5의40도 상품 제외 | 두 API 모두200·빈 목록 | 같은 결과 유지 |

고정 오류 입력 오승인은 **4/4→0/4**, 이 재현 집합의 오승인율은100%→0%로100%p 감소했다.
실사용 자연 오류율·성능 향상·정상 추천 품질/모델 일반화 지표로 해석하지 않는다.

## 선택·비용·한계

기존 수신512KiB/10초 검사 뒤 `object_pairs_hook`가 object별 decoded 이름 중복을 확인한다.
마지막/첫 값 선택·동일 값 허용 대신 중복 전체 거절을 선택했고 escape 동등명도 같은 경계를
적용했다. 서로 다른 상품의 같은 필드명은 정상이며 JSON/+json·Content-Type 생략 의미를
보존했다. key/값을 고정422 메시지에 복사하지 않는다.

표준 decoder의 추가 pass가 있으므로 CPU/메모리 비용은 증가할 수 있다. 입력 크기는 기존
상한을 유지하고 추가 트리를 보관/캐시하지 않으며 별도 속도 개선이나 CPU deadline을 주장하지
않는다. malformed syntax/인코딩·깊이/RecursionError는 정상으로 승인하지 않고 기존 framework의
4xx 경로에 맡긴다. 모델 수치·스키마 검증은 Pydantic이 그대로 소유한다.

PR21 리뷰에서 중복 hook의 즉시 예외가 뒤의 문법 오류보다 먼저 반환되는 경계를 수정했다.
중복은 요청별 flag로만 기록하고 전체 decode 성공 뒤에만 반환한다. 중복 뒤 truncated/trailing/
escape·깊이 오류는 일반 framework 응답과 직접 비교했다. 이 추가 우선순위 검사는 위 유효한
JSON4조건의 전후 정확성 관측과 다른 분모이며 원래4조건 결과를 변경하거나 합산하지 않는다.

근거: [Python JSON의 repeated names/object_pairs_hook](https://docs.python.org/3.12/library/json.html),
[RFC8259 객체 이름의 상호운용성](https://www.rfc-editor.org/rfc/rfc8259#section-4).
