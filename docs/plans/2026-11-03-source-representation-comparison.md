# AI03 — 실제 원천 상품군의 고정 M1 표현 비교

기준 main `b1e7641`에서 기존 source-family 보고서는 TF-IDF fit과 수치 변환·고정 사실 검색을
실행하지만 SVD는 미학습/미채택 상태만 기록했다. 문서상의 후보 선택으로 끝내지 않고, 기존
허용 원천의 실제5×7/rank5에 단일 고정2차원 후보를 실행해 표현 적합성을 비교한다.
이는 별도 오프라인 모델 증가분이며 새로운 API 제공자나 기존 서비스 결함 수정이 아니다.

## 범위와 사전 근거

- 기존 accepted CC0 두 snapshot·각 raw/review/receipt·명시11상품군을 유지한다. 현재6개
  용량 문맥 가족은 GTIN이 없고 ABV는 미지원 generic-percent라 물리 SKU/업무 DEMO로
  승격하지 않는다. [공식 P2665 허용 단위](https://www.wikidata.org/wiki/Property:P2665)는
  volume percent이며 숫자를 유지하려고 의미를 바꾸지 않는다. 새 수집·aT 보류 재시도/우회·
  원천/업무DB/비용/외부 연락은 필요하지 않다.
- 코드 전에 기존 cohort CLI를 실제 재실행해 이전 전체 보고서와 byte 동일함을 확인했다.
  비교 차원/seed·sklearn 알고리즘·반복/oversampling/QR/L2와 측정/기존6질의를 고정했다.
  정확 hash/환경/원값과 두 실행 증거는 [측정 기록](../measurements/2026-11-03-source-representation-comparison.md)에 둔다.
- 서비스 DEMO1상품과 이11 source 상품군의 다른 grain·정체성/누락과 신규 매핑0을 보존한다.
  사용자/미래 로그/외부 평가자 모집을 선행 대기로 삼지 않는다.

## 구현과 대안

새 `source_representation_comparison` CLI는 기존 manifest/receipt/cohort 검증과 fit을 재사용한다.
frozen comparison의 원래 명세·baseline 파일 hash를 확인하고, 현재 원천으로 **baseline 전체를
재계산해 같은 내용인지** 확인한 뒤에만 후보를 fit한다. 기존 B1/HTTP와 원본 보고서는 변경하지 않는다.
별도 candidate TF-IDF·SVD는 학습5상품군만 보고 변환6개는 transform만 한다. 기존 scaler와
수치 unknown은 그대로 보존하고 SVD text branch에 수치 열을 넣지 않는다.

baseline 내부에 옵션을 섞는 대안보다 별도 opt-in CLI/report로 실행/미채택을 구분했다. 모든
자료로 fit하고 다시 나누는 방식은 변환 어휘/스케일 누수라 배제했다. 원차원까지 유지하거나
여러 차원을 held-out 결과에 맞추는 방식 대신, rank보다 작은 사전 고정 후보만 허용한다.
학습 행×열 상한 안에서만 재구성/에너지를 밀집 계산한다.

latent 검색의 음수 cosine은 explicit signed 검사에서만 허용하며 전체 순위/정답/분모 계산기를
재사용한다. 기존 TF-IDF의 비음수 기본 검사는 그대로다. 음수를0으로 자르면 실제 순서가 ID
동점으로 바뀔 수 있으므로 값을 보존하고 확률/서비스 점수로 표시하지 않는다. 새 원자 출력은
기존 파일/경쟁 출력을 덮지 않으며 진단에 원문·개인 경로를 노출하지 않는다.

## 실제 실행과 검증

고정 실제 후보의 학습 재구성 상대 오차0.6993·비중심 에너지51.10%·중심화 설명분산26.72%와
변환 영벡터5/6·OOV6/6을 확인했다. 기존 양성1/전체6질의의 사실 Recall/NDCG는 B1과 같았고
양성 없는5질의는 생략/원순위로 보존했다. 후보 CLI 두 실행의 전체 보고서와 지문은 같고,
baseline 파일/보고서/지문도 그대로다. 정보 손실·지원 범위 불변과 독립 품질 근거 부족으로
운영 미채택을 기록한다. 다른 파라미터를 탐색하거나 지연/품질 성과를 꾸미지 않았다.

Python3.12.14·고정 uv0.13.6의 `./scripts/check.sh` 전체가 성공했다. 저장소 검사·locked sync·
Ruff/format·pytest766개(새38개), 기존 B0/content 시나리오 각8/8·새 sdist/wheel과 runtime-only
격리 설치를 통과했다. checkout 밖 `python -I`의 실제 offline collector/cohort→SVD CLI가
baseline 전체·재현 보고서를 보존했고, 별도 authored held-out 원문/accepted receipt/review/
사실을 바꿔도 학습 파라미터/지문은 같고 transform만 달랐다. stale authority는 고정 exit2와
미발행으로 처리했다. 실제 health/B0/B1/exploration/similar/context/OpenAPI HTTP와 기존
production10초 부분 본문408도 통과했다. 기존 TestClient deprecation 경고1개를 남긴다.
검사 수/CI 시간은 앱 성능 수치가 아니다. README 세 사례 구간은 변경 전과 byte 동일했다.

원문·고정 명세·모델/전체 응답/로그는 ignored에만 보관한다. 최신 head 필수 CI·완료 Codex/
미해결0·Squash/main CI·ff-only/병합 브랜치 정리는 조정자의 최종 게이트이며 현재 로컬 검증
완료와 병합 완료를 구분한다.

## README와 후속

기존 세 사례의 원천 완료 상태·HTTP JSON 의미·수량→실제 scaler 정합성은 관측한 실패와
수정 원인/대안을 설명한다. 이번은 실제 표현 후보를 실행하고 미채택 근거를 확보한 모델 작업이지만
서비스 데이터/독립 관련성·실제 서비스 영향의 더 강한 독립 근거는 아직 없다. 세 사례 본문/순서와
현재3/4·부족1은 보존하고 기능 행만 갱신한다. 테스트 수·새 알고리즘 이름으로 네 번째를 채우지 않는다.

다음은 허용된 완성 포장/변형 정체성·필수 수치·명시 업무 매핑과 다중 서비스 카탈로그/고정
독립 사실 평가다. source 가족 실험·단일 DEMO1·이번 모델 후보를 합산해 전체 AI03/DAT02–04나
서비스 B1/일반화·사람의 선호 품질 완료로 표시하지 않는다.
