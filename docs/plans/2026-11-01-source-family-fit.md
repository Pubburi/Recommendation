# DAT04/AI03 — 실원천 상품군 표현 학습 증가분

- 기준 main `a1f2578`, 작업 `codex/source-family-fit`. Recommendation 단독 쓰기다.
- 공식 원천을 추가 조사했지만 포장/용량별 SKU 근거는 확보하지 못했다. CC0의 명시 검수 상품군5를
  서비스 SKU로 바꾸지 않고 source QID·family grain의 오프라인 표현 실험으로 진행한다.
- OFF 공식 문서는 ODbL/DBCL·이미지 별도 CC BY-SA·API 사용 전 usage form을 안내한다.
  CC0와 같다고 가정하지 않았고 폼/외부 연락·데이터 수집은 하지 않는다. 현재 정본의 기본 미승인과
  aT 특정 POST 보류/우회 금지·비용/키/가입/AWS 경계는 유지한다.
- 최초 fit 전 실제 원천 P31/P176·ABV/volume 사실·명시 그룹의 학습3/변환2를 수동 동결했다.
  receipt/evidence binding 추가 시에도 사실/분할은 바꾸지 않았다. 관련성 정답을 모델로 만들지 않는다.
- `source_family_experiment`가 권리·원문/검수/receipt/manifest/spec hash·정확 ID/revision/API 오류·
  명시 product_family·사실/분할을 확인하고 TF-IDF/관측 수치 변환을 fit한다. 기존 서비스
  ContentProduct·B0/B1 HTTP/API·Backend 숫자 ID·추천 순위는 변경하지 않는다.
- 실제 fit3/transform2, TF-IDF3×5/rank3·학습 ABV3관측5.5–10%·volume0관측/all_unknown을 확인했다.
  변환 주종2토큰 OOV/공유제조사만지원·도수범위밖1/2·volumeunknown2/2를 기록했다.
  [원값·버전·한계](../measurements/2026-11-01-source-family-fit.md)는 성능/사람 선호 성과가 아니다.
- 독립 DF/IDF·학습 수치 범위·held-out 변화 시 fit 상태 불변·상수0/unknown·빈 어휘·상품군 교차/
  브랜드/사실 모순·권리/receipt/hash·원자 출력/보존을 자체 fixture로 검증한다. 실제 원문·카탈로그·
  파라미터는 ignored, CI는 authored_regression_fixture만 새 wheel runtime-only CLI로 실행한다.
- 실카탈로그 표현의 제한을 실제로 확인했지만 서비스 SKU/실서비스 B1 fit·관련성/최종 평가·
  Backend/웹 연동·DAT04/AI03 전체 완료는 아니다. M1은 작은 실제 차원/rank와 독립 목적 평가
  부족으로 이번엔 미채택/미fit, Recall/NDCG도 독립 관련성 라벨 부재로 미산출이다.
- README 사례는 기존2/4를 보존한다. 실제 원천 표현 fit/누수 증거는 늘었지만 서비스 결과나
  독립 관련성 평가가 없어 REC-CS04 완료나 더 강한 대표 사례로 승격하지 않는다.
- 한국어 한 목적 feat 커밋 뒤 SHA·PR 초안/검증 근거를 인계한다. root가 PR/리뷰/CI/병합/
  main CI·브랜치 삭제·Notion·lease 해제를 담당한다.
- 첫 전체 검증은 pytest311·B0/B1각8/8 뒤 runtime fixture의 P2665 snaktype 누락으로
  사실 대조가 실패했다. 미확인 수치로 보존된 자체 입력을 고치고 실패를 숨기지 않은 채 전체를
  다시 검증했다. collector manifest 모델 해시/파일 바이트 해시도 실제 receipt로 구분했다.
- 최종 코드의 전체 `check.sh`는 locked/Ruff·pytest311(새25회귀)·B0/B1각8/8·새 sdist/wheel의
  runtime-only 실제 수집→상품군 fixture2fit/1transform·기존 원천 오류/깊은JSON/legacy감사/B1fit·
  실제 health/B0/OpenAPI/중복ID422를 통과했다. 기존 TestClient 경고1건은 남아 있다.
  최종 실제 원천 CLI 재실행도 이전 파라미터/fingerprint·변환 결과와 같았다.
