<div align="center">
  <img src="docs/brand/pubburi.webp" alt="주점부리" width="96" />
  <h1>주점부리 · Recommendation</h1>
  <p><strong>취향에 맞는 한 잔을 발견하고 기록하는 주류 큐레이션</strong></p>
  <p>Python·FastAPI 기반 추천 서비스</p>
  <a href="https://github.com/Pubburi/Recommendation/actions/workflows/ci.yml"><img src="https://github.com/Pubburi/Recommendation/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI" /></a>
  <img src="https://img.shields.io/badge/Python-3.12-3776AB" alt="Python 3.12" /> <img src="https://img.shields.io/badge/FastAPI-009688" alt="FastAPI" /> <img src="https://img.shields.io/badge/uv-DE5FE9" alt="uv" />
</div>

<br />

## 📄 목차

- [프로젝트 개요](#overview)
- [현재 기능과 범위](#features)
- [기술 스택](#technology)
- [시스템 구조](#architecture)
- [문제 해결](#problem-solving)
- [로컬 실행](#development)
- [검증과 협업](#verification)
- [개발 계획](#roadmap)

<br />

<a id="overview"></a>

## ✍ 프로젝트 개요

주점부리의 Python·FastAPI 서버입니다. 현재 헬스 체크·API 문서·패키징·CI를 제공하며, 상품 추천과 모델 학습은 개발 계획에 따라 구현합니다.

<a id="features"></a>

## 🥃 현재 기능과 범위

| 기능 | 제공 내용 |
|---|---|
| 헬스 체크 | GET /health → 상태와 서비스 이름 반환 |
| API 문서 | FastAPI 자동 생성 /docs와 /openapi.json |
| 독립 실행 | DB·모델 파일·외부 AI 키 없이 기동 |
| 품질 검사 | Ruff, pytest, wheel·sdist 빌드 |

<a id="technology"></a>

## ⚙️ 기술 스택

| 영역 | 기술 |
|---|---|
| 런타임 | Python 3.12 |
| 서버 | FastAPI, Uvicorn |
| 의존성·패키징 | uv, uv.lock, pyproject.toml, Hatchling |
| 테스트·검사 | pytest, HTTPX, Ruff |
| CI | GitHub Actions · recommendation-ci |

<a id="architecture"></a>

## 🏛️ 시스템 구조

~~~mermaid
flowchart LR
    Web["웹 클라이언트"] -. "후속 기능" .-> Backend["Backend"]
    Backend -. "후속 추천 API 연동" .-> API["Recommendation · FastAPI"]
    API --> Health["/health · 현재 구현"]
    API -. "후속 구현" .-> Model["특성 처리 · 추천 · 학습 · 평가"]
~~~

<a id="problem-solving"></a>

## 🧩 문제 해결

### 모델 준비와 프로세스 가용성을 분리한 헬스 계약

#### 문제

추천 기능을 개발하기 전에도 서버가 실행되고 요청에 응답하는지 확인할 수 있어야 했다. 모델 파일·상품 데이터·DB 연결을 서버의 기본 기동 조건으로 삼으면, 자원 준비와 프로세스 상태를 함께 다뤄야 한다.

#### 원인

프로세스가 요청을 받을 수 있는 상태와 추천을 계산할 준비가 된 상태는 서로 다른 조건이다. 초기 서버에는 추천 모델과 데이터 계약이 없으므로 이를 헬스 응답에 포함하면 확인되지 않은 준비 상태를 정상으로 표현할 수 있다. 이는 관측한 장애를 복구한 사례가 아니라, 초기 구현에서 진단 범위를 정한 설계 문제다.

#### 해결

앱 생성과 `/health` 처리에서 모델·DB·외부 API를 읽지 않도록 경계를 잡았다. 헬스 응답은 프로세스 상태와 서비스 이름만 제공하고, 현재 구현 범위를 API 설명에도 기록했다.

#### 결과

현재 서버는 모델 파일·학습 데이터·외부 AI 키 없이 헬스 응답을 제공한다. 응답의 의미는 요청 처리 가능 여부이며, 추천 결과나 모델의 준비·품질은 별도 계약으로 다룬다.

#### 대체안/회고

헬스 요청에서 모델을 불러오거나 DB까지 조회하면 추천 준비 상태도 함께 검사할 수 있지만, 호출 지연과 외부 자원의 실패가 프로세스 진단에 섞인다. 모델 연동 단계에서는 프로세스 가용성과 추천 준비 상태를 구분하고, 준비되지 않은 이유와 대체 추천 동작을 연결할 필요가 있다.

#### 코드

앱 생성과 현재 헬스 처리의 전체 흐름이다. [현재 구현](https://github.com/Pubburi/Recommendation/blob/main/src/pubburi_recommendation/main.py)

~~~python
from fastapi import FastAPI

app = FastAPI(
    title="Pubburi Recommendation",
    description="Service bootstrap. Recommendation algorithms are planned separately.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Report process availability without requiring a database or a model."""
    return {"status": "ok", "service": "pubburi-recommendation"}
~~~

<a id="development"></a>

## 🚀 로컬 실행

Python 3.12와 uv 0.13.6을 사용합니다. 레포 루트에서 실행합니다.

세 서버와 DB를 함께 실행하는 방법은 [로컬 통합 실행](https://github.com/Pubburi/Backend/blob/main/docs/LOCAL-DEVELOPMENT.md)을 참고하세요.

~~~bash
uv sync --locked
./scripts/dev.sh
~~~

- 서버: http://localhost:8000
- 개발 포트: PUBBURI_RECOMMENDATION_PORT(기본 8000)
- 헬스 체크: http://localhost:8000/health
- API 문서: http://localhost:8000/docs
- 현재 필수 환경변수와 외부 서비스는 없습니다. .env.example에 현재 요구사항을 기록했습니다.
- 데이터·모델 파일을 시작 시 자동 다운로드하지 않습니다.

<a id="verification"></a>

## ✅ 검증과 협업

~~~bash
./scripts/check.sh
~~~

고정 의존성을 설치하고 Ruff·pytest·배포 파일 빌드를 실행합니다. 테스트는 DB·모델 없이 HTTP 서비스가 기동하고 헬스 계약을 제공하는지 확인합니다. 빌드 파일 생성은 실제 서버 배포를 뜻하지 않습니다.

main은 PR·recommendation-ci 성공·최신 main 반영·대화 해결을 요구합니다. 필수 승인은 0명이고 관리자에게도 적용합니다. Squash merge 뒤 작업 브랜치를 정리합니다.

자동화 PR은 최신 커밋의 Codex 리뷰와 관련 검증까지 통과해야 병합합니다. [추천 개발·운영 기준](AGENTS.md)을 함께 적용합니다.

<a id="roadmap"></a>

## 🗺️ 개발 계획

기한은 **2027년 2월 5일**이며 P1·P2 추천 모두 필수 목표입니다. [추천 데이터·모델·평가 계획](docs/DATA-AND-MODEL-PLAN.md)을 기준으로 진행합니다.

- [ ] 상품 특성·사용자 취향·평점·찜 데이터 계약 정리
- [ ] 콘텐츠 기반 추천·유사 상품·신규 사용자 대체 추천
- [ ] 추천 이유·관심 없음 반영과 Backend API 연동
- [ ] 검수 카탈로그로 특성·TF-IDF 모델을 실제 fit하고 학습·검증·최종 평가를 분리
- [ ] 기본순·콘텐츠 기준선과 비교하고, 고정 사실 시나리오 평가와 실제 사용자 선호를 구분
