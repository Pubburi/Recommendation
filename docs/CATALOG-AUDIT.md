# 원천·단위·상품 정체성 감사

`python -m pubburi_recommendation.catalog_audit`는 로컬 JSON을 읽는 오프라인 도구다.
네트워크 요청·학습·DB 변경·원본 자동 다운로드를 하지 않는다. 현재 지원하는 실제 입력은
Wikidata `wbgetentities`의 item JSON이며, 원천 명세는 `sources/`에 둔다.

## 권리·처리 범위

- [Wikidata 공식 라이선스](https://www.wikidata.org/wiki/Wikidata:Licensing)는 구조화 데이터를
  CC0로 제공한다. 명시적으로 확인한 item 라벨·P31/P176 식별자·P2665 도수·P2234 용량만 처리한다.
  다른 문서 본문·연결된 사진/이미지·외부 사이트의 권리로 확대하지 않는다.
- [데이터 접근 문서](https://www.wikidata.org/wiki/Wikidata:Data_access)를 확인하고 식별 가능한
  User-Agent로 소수 항목을 조회했다. API 계정/키·대량 덤프·이미지는 사용하지 않았다.
- 원천 명세는 담당자의 증거와 사용 결정을 기록한다. 프로그램이 법적 권리를 판정하거나
  새 권한을 부여하는 장치가 아니다. 미확인 원천은 먼저 보류하고 데이터 파일도 읽지 않는다.
- 원본·정규화 전체 데이터·검수 mapping은 Git에 넣지 않는다. CLI는 `.pubburi` 경로 아래의
  새 출력 폴더만 허용하고 기존 실행 결과를 덮어쓰지 않는다. 공유 가능한 근거는 명세·코드·
  직접 작성한 작은 테스트 입력·집계와 한계다.

### aT 전통주정보의 현재 확인 상태

[공식 상세](https://www.data.go.kr/data/15048755/fileData.do?recommendDataYn=Y)에서 파일명
20260731, 수정일 2026-10-22, 16컬럼·1251행, 무료/이용허락범위 제한 없음과 판매자 허락·
상업적 이용 전 협의·공란 가능 유의사항을 확인했다. **이는 포털 메타데이터이며 파일 실측이 아니다.**

다운로드 전 메타데이터를 얻는 공개 버튼의 POST가 자동 승인 검토에서 거절됐다. 검토 사유는
제3자 권리와 학습/재배포 조건 미확정 상태의 실제 응답 저장 위험이었다. 이 요청을 우회하거나
재시도하지 않았고 aT CSV는 받지 않았다. `sources/at-traditional-liquor.json`에는 이번 획득·
권리 확인의 보류 상태를 남겼다. **상업적 이용 전 협의 문구만으로 현재 비상업 사용이 금지된다는
일반 규칙으로 해석하지 않는다.** 추가 권리/검토 문제가 해결되면 별도로 갱신한다.

메타데이터의 도수1–3/용량1–3을 서로 곱해 SKU로 만들 수 없고, 공개된 컬럼에는 가격·사용자
선호·정량 맛 점수와 명시적인 주종 컬럼도 없다. 제품소개·특징 같은 원문은 구조화 수치와 권리를
구분해 다뤄야 한다. [포털 정책](https://www.data.go.kr/ugs/selectPortalPolicyView.do)도 함께 검토했다.

## 단위·범위·정체성

- [P2665](https://www.wikidata.org/wiki/Property:P2665)는 명시된 volume-percent 단위만
  0–100 도수로 받는다. 무단위·미지원 단위·비유한 값·범위·문맥 qualifier·서로 다른 여러 값은
  unknown과 검토 사유로 남긴다. 0%는 미확인 값과 다르다.
- [P2234](https://www.wikidata.org/wiki/Property:P2234)는 mL·L·cL을 Decimal로 mL로 바꾼다.
  용량은 0 초과·1,000,000 mL 이하를 허용하고 표현 과정의 언더플로를 0으로 대체하지 않는다.
  값이 서로 충돌하거나 수량 범위/문맥이 있으면 하나의 용량이나 여러 SKU로 추측하지 않는다.
- deprecated statement는 계산에 사용하지 않는다. 참조한 entity ID·revision·공식 URL과
  입력 파일 SHA-256을 남긴다. 라벨 없는 항목은 임의 이름을 만들지 않는다.
- P31의 주종·브랜드·생산자·제품군을 개별 판매 SKU와 구분한다. QID를 Backend의 상품 ID로
  바꾸거나 용량/도수의 조합으로 가짜 SKU를 생성하지 않는다. 가격·판매 가용성·맛은 추론하지 않는다.

## 실행·출력

자신이 권리를 확인해 준비한 Wikidata JSON 경로를 입력한다. HTTP 획득은 CLI와 분리하며
조회한 entity/revision·접근 시각·원문 해시를 ignored 획득 기록에 보관한다.

```bash
uv run --locked python -m pubburi_recommendation.catalog_audit \
  --manifest sources/wikidata-structured.json \
  --input .pubburi/source-audit/wikidata/entities.json \
  --output-dir .pubburi/source-audit/wikidata/new-run
```

- `audit-report.json`: 입력 해시·레코드 수·종류·결측·수량 검토 사유·B0 내보내기 수와 한계.
- `normalized-records.json`: 허용한 구조화 필드·출처/revision·unknown·검토 결과. 원문 본문/이미지는 없음.
- `--review`를 제공한 경우 `b0-demo-request.json`: 검수된 개별 SKU만 B0 계약으로 변환한
  **시연 전용** 요청. 검수 없이 자동으로 상품을 만들지 않으며 이 산출물은 업무 DB의 상품 원본이 아니다.

입력은 최대 10 MiB·2000 entity다. 원문 해시가 바뀌면 검수 mapping을 재확인한다.
내보내기는 기존 B0의 1000상품·ID 중복·범위 계약으로 다시 검증한다. 오류 출력에는 원문 입력·
개인 경로·검수 내용이 노출되지 않는다.

## 검수 mapping

아래는 실제 주류가 아닌 문법 설명용 예시다. 모든 항목은 알려진 입력 QID만 참조해야 한다.
`input_sha256`는 실제 입력 파일 해시로 바꾼다. `kind`가 `sellable_sku`인 경우만 내보내며,
Backend 상품 ID·명시적 시연 가용성·검수한 SKU 그룹·라벨을 요구한다. 주종은 명시적으로
검수한 값만 쓰고, 시연 가격은 별도 `demo_price_krw`로 기록해 원천 관측값과 섞지 않는다.

```json
{
  "input_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "catalog_mode": "demo",
  "records": {
    "Q1": {
      "kind": "sellable_sku",
      "evidence_url": "https://example.org/fictional-fixture",
      "backend_product_id": 11,
      "demo_available": false,
      "demo_price_krw": null,
      "reviewed_category": null,
      "reviewed_sku_group": "fictional-reviewed-family"
    }
  }
}
```

이 그룹은 사람의 명시적 검수 입력이다. 서로 다른 원천/브랜드/용량 변형의 누수 방지 그룹이
완성됐다는 뜻은 아니며 학습 전 별도 SKU/변형 감사를 계속해야 한다.

## 실제 소량 표본 결과와 한계

2026-10-31 목적 표본은 Q16219738·Q194297·Q3624753·Q140199255의 4항목이다.
구조화 정보와 검색 결과를 검토해 브랜드 3·정체성 미확정 1로 분류했으며 검수 SKU는 0이다.

| 항목 | 실측 결측/전체 |
|---|---|
| 한국어/영어 라벨 | 1/4 |
| 지원 단위의 단일 도수 | 1/4 |
| 단일 용량 | 4/4 |
| 실제 가격 | 4/4 |
| 검수 SKU 그룹 | 4/4 |

도수가 있는 브랜드도 특정 용량·판매 SKU의 사실로 사용하지 않았다. B0 시연 내보내기는
**0건**이다. 이 목적 표본의 충실도를 Wikidata 전체나 국내 주류 전체의 비율로 일반화하지 않는다.
원본은 ignored에만 있고, 집계는 실제 CLI가 계산했다. B1 fit·원천 카탈로그 완성·추천 품질은
이번 결과가 아니며, 실제 서비스 상품/권리·단위·SKU 연결을 다음 단계에서 확보해야 한다.
