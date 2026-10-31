# 기본 라벨 누락의 동일 revision 비교

## 문제·조건과 원인

기준 커밋은 `19e1dae`다. 2026-10-31 23:38 UTC에 기존 maxlag5·고정 HTTPS·단일 GET·10-ID/
10MiB/timeout/프레이밍 경계를 유지한 원천 복구 확인이 성공했다. 이후 공식 Wikidata 생산자와
상품 링크에서 고른 **명명된 맥주 상품군5·브랜드1**의 목적 표본을 확보했다. 포장/용량별 판매 SKU가
아니며 한국 서비스나 Wikidata 전체의 품질·충실도를 대표하는 무작위 표본도 아니다.

기존 요청은 `languages=ko|en`, 정규화도 ko/en만 검사했다. 실제 항목 중3개는 두 언어 라벨이
없고 원천의 기본 라벨만 있어 이름이 null이 됐다. [공식 기본값 명세](https://www.wikidata.org/wiki/Help:Default_values_for_all_languages)는
API에서 `mul`을 요청하면 여러 언어의 공통 기본 라벨을 받을 수 있다고 설명한다. 설명/별칭·
다른 웹사이트의 이름을 복사하거나 번역하는 대안보다 원천이 제공하는 구조화 기본값을 선택했다.

## 비교 방법과 관측값

두 GET은 같은6QID·동일 source revision6/6·동일 비라벨 entity 필드6/6였다. 요청의 라벨 언어와
정규화 선택만 바꿨다. 네트워크 지연이나 추천 점수는 비교하지 않았다. snapshot·영수증·revision별
검수 mapping·계산 JSON은 ignored에 보존하고 개별 카탈로그/원문은 Git에 올리지 않는다.

| 조건/지표 | 변경 전 | 변경 후 |
|---|---|---|
| UTC 관측 | 2026-10-31 23:38:51 | 2026-10-31 23:39:43 |
| 요청 언어 | ko/en | ko/en/mul |
| 선택 순서 | ko → en | ko → en → mul |
| 표본 수 | 6 | 6, 같은 항목·revision |
| 원문 크기 | 68,970 B | 69,218 B |
| 라벨 결측 | 3/6 (50%) | 0/6 (0%) |
| 선택한 라벨 언어 | en3·unknown3 | en3·mul3 |
| 지원 단위의 단일 도수 결측 | 1/6 | 1/6 |
| 용량·가격·검수 SKU 그룹 결측 | 각각6/6 | 각각6/6 |
| 판매 SKU/B0 내보내기/실카탈로그 fit | 각각0 | 각각0 |

라벨 결측은 **50%p 감소**했다. 이는 작은 고정 표본에서 실제 원천 이름의 유실을 줄인 정확성
결과이며 응답 속도·모델 추천 품질·사람의 만족도·서비스 장애율 개선이 아니다. 원문은 248B
늘었고 언어 출처 필드를 보관하는 부담도 추가됐다. 이미 존재하던 ko/en 선택은 변경하지 않았다.

- 변경 전 원문 SHA-256: `b38d6dbd6acfd76b9e9633251077eb4305c8535c7767adaf7c3877aeee5a8c89`
- 변경 후 원문 SHA-256: `7250e348a35485201f728e87c97f633e7bf34bb77e69241695308055b3acf6ca`

원천 라벨의 존재는 실제 판매 SKU·특정 용량/도수 변형의 동일성이나 최신 사실의 정확성을
보장하지 않는다. 상품군5의 도수는 허용 단위의 단일 구조화 statement로 정규화했지만 해당 포장 SKU를
만들지 않았다. 브랜드1의 도수는 일반 percent 단위여서 기존 정책대로 unknown/unsupported_unit로
보존했다. 원천 참조가 가리키는 외부 사이트·원문·이미지·평점·인기 수치는 요청하거나 특성으로 쓰지 않았다.

## 재현과 검수 경계

기존 `wikidata_collect`의 같은6-ID 명령에서 언어 목록만 코드로 바꾼 두 영수증을 사용했다.
수집 성공/원문 해시·정확 ID/revision 확인 후 아래처럼 같은 snapshot을 오프라인으로 재검사한다.
명령의 입력/검수 파일은 보존한 비공개 원본을 사용하며 미래 원천의 값으로 과거 결과를 대체하지 않는다.

~~~bash
uv run --locked python -m pubburi_recommendation.catalog_audit \
  --manifest sources/wikidata-structured.json \
  --input .pubburi/entity-catalog/h7-named-beer-default-labels-live/entities.json \
  --review .pubburi/entity-catalog/h7-named-beer-default-labels-review.json \
  --output-dir .pubburi/entity-catalog/new-default-label-audit
~~~

집계는 다음 규칙으로 계산한다. 원문 해시가 서로 달라 같은 revision이라도 이전 검수 mapping은
새 원문에 재사용하지 않는다. 실제 CLI에서 이전 mapping은 `review_snapshot_hash_mismatch`/
종료2·출력 미생성으로 보류되고 새 해시에 명시한 상품군/브랜드 검수만 통과했다.

~~~python
import json
from pathlib import Path

root = Path(".pubburi/entity-catalog")
old_dir = root / "h7-named-beer-families-live"
new_dir = root / "h7-named-beer-default-labels-live"
load = lambda path: json.loads(path.read_text())
old_raw = load(old_dir / "entities.json")["entities"]
new_raw = load(new_dir / "entities.json")["entities"]
assert old_raw.keys() == new_raw.keys()
for qid in old_raw:
    assert old_raw[qid]["lastrevid"] == new_raw[qid]["lastrevid"]
    assert {k: v for k, v in old_raw[qid].items() if k != "labels"} == {
        k: v for k, v in new_raw[qid].items() if k != "labels"
    }
before = load(old_dir / "normalized-records.json")
after = load(new_dir / "normalized-records.json")
missing = lambda rows: sum(row["label"] is None for row in rows)
assert len(before) == len(after) == len(old_raw)
percentage_point_reduction = (missing(before) / len(before) - missing(after) / len(after)) * 100
print(missing(before), missing(after), len(after), percentage_point_reduction)
~~~

현재 비교의 원문에는 label 집합만 달라졌다. 이미 mul이 포함된 다른 과거 원문에 새 정규화 코드를
적용할 때에는 raw 해시가 같다는 이유만으로 그 projection의 의미까지 재검수됐다고 가정하면 안 된다.
기존 normalized 파일을 덮어쓰지 않고 새 출력과 코드 버전/선택 언어를 함께 확인한다.

이 실행의 새 고유 source entity는 복구 확인1개와 표본6개를 합한7개다. 전후 재조회6개를 다시
새 상품으로 합산하지 않는다. 기존4항목·legacy80행과도 모집단/단위가 다르다. 실제 서비스 SKU,
서비스 카탈로그 fit·관련성 라벨/최종 평가, Backend/Frontend 연동은 여전히 미완료다.
