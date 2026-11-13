# Recommendation 문제 해결 사례

README에는 실제 서비스 연동에서 재현한 대표 사례 한 건을 둔다. 이 사례는 처음 개인화 추천이 요청 제한을 넘겨 대체 응답으로 바뀌는 현상을 동일 설치·입력에서 재현했다. 변경 뒤 결과가 보존됐는지 확인했고, 준비 시간이 헬스 체크 앞으로 이동한 비용도 기록했다.

| ID | 현재 사례 | 근거 |
|---|---|---|
| REC-CS08 | health 뒤 첫 B1의 요청 예산 초과를 lifespan 준비 경계로 이동 | [동일 설치/입력의 원값과 startup 비용](measurements/2026-11-08-b1-startup-boundary.md)·[측정값](measurements/2026-11-08-b1-startup-boundary.json)·[실제 lifespan](../src/pubburi_recommendation/main.py) |

이전에 소개한 수집 오류, 중복 JSON, 수량 해석 사례는 [이전 사례와 근거](https://github.com/Pubburi/Recommendation/blob/e1df07355d67331560eb2e0e37c21f64d45287ab/docs/case-study-register.md)에서 확인할 수 있다.
