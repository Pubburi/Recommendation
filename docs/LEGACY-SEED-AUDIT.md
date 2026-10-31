# 기존 시드·상품 이미지 감사

`legacy_seed_audit`는 기존 상품 시드와 로컬 이미지의 읽기 전용 인벤토리·격리 도구다.
SQL 실행·DB 연결·크롤링·이미지 변환·학습·상품 생성은 수행하지 않는다. 기존 값과 별도 검수/권리
근거를 분리하고, 시드를 검수 카탈로그나 관측 사용자 행동으로 자동 승격하지 않는다.

## 실제 조사 범위와 결과

2026-11-01 한국 시간에 [Backend 75b30c3의 SQL](https://github.com/Pubburi/Backend/blob/75b30c32a51685dec8be8120343c1d7c0e7644a7/data.sql)과
[Frontend a94346a의 pub 자산](https://github.com/Pubburi/Frontend/tree/a94346a7a4cb2d068e94af0582a5b6cd237e0c9d/public/images/pub)을 감사했다.
[실제 웹 매핑 함수](https://github.com/Pubburi/Frontend/blob/a94346a7a4cb2d068e94af0582a5b6cd237e0c9d/src/utils/format.js)를
별도 Node 실행으로 호출해 매핑·일반 파일·SHA-256을 다시 대조했다. SQL은 고정 Git blob을 임시로
읽고 삭제했으며 사용자/암호 행은 보고서나 원문 스냅샷으로 보관하지 않았다.

| 확인 단위 | 실제 결과·분모 | 해석 |
|---|---|---|
| 활성 상품 INSERT | 8문장·80행 | 주석의 옛5상품 제외. 행 순번은 현재 DB ID/검수 SKU가 아님 |
| 시드 값 형태/범위 | 이름·주종·가격·도수·order_count 각각80/80 유효 | 채워진 값이며 사실·신선도·허락 검증은 별도 |
| 시드 주종 | 8종 각각10행 | 시드 분류이며 실제 상품 분류 정답으로 승인하지 않음 |
| 동일 literal 값·정규화 이름 중복 | 각각0/80 영향 행 | 실제 상품 변형/SKU 중복이 없다는 결론으로 확대하지 않음 |
| WebP 매핑·일반 파일·해시 일치 | 각각80/80행 | 실제 Frontend 함수와 대조. 원래 PNG는0/80이지만 현재 웹 링크 누락이 아님 |
| 공유 매핑 참조·동일 바이트 파일 | 각각0그룹 | 시각적 동일성·상품 대응·허락을 뜻하지 않음 |
| 참조되지 않은 pub 일반 파일 | 0/80파일 | category/banner/brand 등 다른 디렉터리는 조사 범위 밖 |
| 개별 상품 단위·필드 사실 근거 | 80/80행 미확인 | 값이 있어도 원천·변형·확인 시점 근거가 연결되지 않음 |
| 검수 용량·SKU그룹·맛/향 | 각각80/80행 미확인 | 이름 속 mL·%·브랜드나 파일명으로 채우지 않음 |
| 실제 가격·관측 인기 | 각각80/80행 미확인 | 기존 가격·order_count는 시연 값으로 분리 |
| 개별 이미지 사용 조건 근거 | 80/80참조 파일 미확인 | 소스 이전/Git 이력을 제3자 이미지 허락으로 해석하지 않음 |
| 학습 승격 | 0/80행 | 전부 격리. 실제 서비스 SKU/모델 학습 완료가 아님 |

입력 SQL SHA-256은 `508e24a2fb2f2c5dd3e33e9d0b93664847936a7380bc04fde1c0e76e5775e032`,
정렬 자산 인벤토리 SHA-256은 `b300636afdab1478dd2564feee819e70b5749dcb8b100efae4920d76632bc70e`다.
독립 문장/행 계수와 실제 웹 함수 대조는 모두 일치했다. 개별80행·파일명/해시는 ignored에만 두고
집계만 공유한다. 다른 버전은 자기 입력 해시로 다시 판단한다. 이 수치는 품질 감사의 현황이며
변경 전후 성능 개선이나 운영 오류율이 아니다. 시간 경과/신선도 추이는 조사하지 않았다.

## 출처·사용 목적의 분리

[Backend](https://github.com/Pubburi/Backend/blob/75b30c32a51685dec8be8120343c1d7c0e7644a7/docs/PROVENANCE.md)·
[Frontend](https://github.com/Pubburi/Frontend/blob/a94346a7a4cb2d068e94af0582a5b6cd237e0c9d/docs/PROVENANCE.md)의
PROVENANCE는 기존 프로젝트와 Git 이력의 출처를 설명한다. 조사한 시드/문서에는 개별 상품 사실의
원천·확인 시점·판매 용량/변형, 이미지별 작성자·허락·라이선스가 연결되어 있지 않았다. 현재 조사
범위에서 근거가 미확인이라는 상태이며 법적 권리의 유무를 자동 판정하지 않는다.

`sources/legacy-demo-seed.json`은 로컬 inventory만 수행하는 결정을 기록한다. 학습·공개 재배포·
이미지 재사용 플래그는 false로 고정하며 true로 바꾸어도 이 도구가 승인 상태를 생성하지 않는다.
원문 가격은 `demo_price_krw`, 주문 수는 `demo_order_count`, 도수는 `unverified_abv_percent`다.
Backend ID·검수 SKU그룹/용량/주종/도수·맛/향·실제 가격/인기는 null이며 `feature_fit_eligible`은
false다. B0/B1 요청을 내보내거나 서버 시작 때 로드하지 않는다.

다음 검수는 허용 원천의 개별 사실/SKU 매핑과 이미지별 조건 확인 또는 자체 제작/허용 대체 자료다.
현재는 사실·단위·출처 검수를 새로 확보해야 하는 단계다. 기존 Backend/Frontend 데이터·자산은
수정하거나 삭제하지 않았다. 원천 권리와 실제 주류 품질·사람의 선호를 추정하지 않는다.

## 실행과 안전 경계

~~~bash
uv run --locked python -m pubburi_recommendation.legacy_seed_audit \
  --manifest sources/legacy-demo-seed.json \
  --sql ../Backend/data.sql \
  --assets-dir ../Frontend/public/images/pub \
  --output-dir .pubburi/legacy-audit/new-run
~~~

SQL은10MiB·상품2,000행, 자산은2,000개·개별20MiB·총128MiB로 제한한다. `.pubburi` 아래 새
디렉터리에 `audit-report.json`, `quarantined-products.json`, `asset-inventory.json`만 생성한다.
사용자/암호 행은 저장하지 않고 제품의 지정 여섯 필드만 처리한다. stdout은 집계, 오류는 고정
진단 코드/오류 종류만 출력한다. 종료값은 실행 성공0·실패2이며 성공은 권리/학습 승인이 아니다.

제한된 파서는 활성 `t_product`의 명시 컬럼 `(name,type,price,img,abv,order_count)` literal
INSERT만 받는다. 컬럼 순서 변경·단일 따옴표/겹따옴표 escape·정수/소수·NULL·일반 주석을 지원한다.
함수/SELECT/변수/수식·backslash escape·실행 주석·지원하지 않는 INSERT는 거절한다. CTE 변경문·
LOAD·RENAME을 포함해 변경문에 t_product 식별자가 언급되면 보수적으로 보류한다. 문자열 값의 같은 단어와
읽기 전용 CTE는 구분한다. 일반 MySQL 파서/DB 실행 결과를 대신하지 않는다.
[공식 주석](https://dev.mysql.com/doc/refman/8.4/en/comments.html)·
[문자열](https://dev.mysql.com/doc/refman/8.4/en/string-literals.html) 규칙을 확인해 지원 부분을 정했다.

현재 pub basename·`/images/pub/`만 지원하고 PNG/JPEG 참조를 WebP로 매핑한다. 경로 탈출·외부 URL·
다른 디렉터리·query/fragment를 읽지 않으며 디렉터리 fd·NOFOLLOW로 root/leaf 교체·symlink를 차단한다.
하위 폴더를 순회하지 않는다. 원본/변환 파일은 서로 다른 해시로 보존한다. 시그니처는 헤더 확인이며
디코딩/화면·상품 동일성·권리 검증이 아니다.

자산은 fstat 크기로 초과 파일을 본문 읽기 전에 보류한다. 읽기 도중 크기가 바뀌거나 크기 정보가
오래된 경우에도 남은 총예산 이내에서만 읽으며, 거절/실패한 파일의 실제 읽은 바이트까지 예산에
포함한다. 공개 인벤토리의 파일 크기·해시와 내부 I/O 예산 계수는 별개다.

중복은 정확한 Decimal 값·정규화 이름·공유 이미지 참조·동일 바이트 그룹으로 나눈다. 숫자 문자열과
숫자 literal을 혼동하거나 Decimal precision으로 값을 반올림해 합치지 않는다. 작은 양수 도수가
float0으로 언더플로하면 unknown으로 보존한다. 자동 병합·보정·상품 추론은 없다.

[테스트·격리 배포 검증](TESTING.md)은 작은 자체 fixture만 쓴다. 실제80행/이미지를 CI에 복사하거나
80이라는 개수를 단위 정답으로 고정하지 않는다. DAT01/02 초기 감사 증가분이며 허용 서비스 SKU·
개별 사실/권리 해결·B1 실카탈로그 fit은 미완료다. Wikidata4항목과 시드80행은 별도 모집단/단위다.
