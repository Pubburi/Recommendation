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
- [로컬 실행](#development)
- [검증과 협업](#verification)
- [개발 계획](#roadmap)
- [관련 프로젝트와 개발자](#links)

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

자동화 PR은 최신 커밋의 Codex 리뷰와 관련 검증까지 통과해야 병합합니다. [개발·운영 기준](https://github.com/Pubburi/Backend/blob/main/docs/DELIVERY-PLAN.md)을 함께 적용합니다.

<a id="roadmap"></a>

## 🗺️ 개발 계획

기한은 **2027년 2월 5일**이며 P1·P2 추천 모두 필수 목표입니다. [전체 기능·일정](https://github.com/Pubburi/Backend/blob/main/docs/DELIVERY-PLAN.md)을 기준으로 진행합니다.

- [ ] 상품 특성·사용자 취향·평점·찜 데이터 계약 정리
- [ ] 콘텐츠 기반 추천·유사 상품·신규 사용자 대체 추천
- [ ] 추천 이유·관심 없음 반영과 Backend API 연동
- [ ] 공개 데이터에서 학습·검증·최종 테스트를 분리한 모델 실험
- [ ] 인기순 기준선과 비교하고, 시연용 합성 데이터와 실제 평가 결과 구분

<a id="links"></a>

## 🔗 관련 프로젝트와 개발자

| 레포 | 담당 |
|---|---|
| [Backend](https://github.com/Pubburi/Backend) | 회원·상품·후기·데모 주문 및 공통 API |
| [Frontend](https://github.com/Pubburi/Frontend) | 현재 Vue 웹·관리자 화면, 향후 React 전환 |
| [Recommendation](https://github.com/Pubburi/Recommendation) | 추천 서비스 기반, 향후 데이터·알고리즘·평가 |

[기획·해야 할 일](https://www.notion.so/3ff86a7a8f8a80d298adfd1b0e0c6ae6) · [협업 규칙](CONTRIBUTING.md)

| 개발자 | 이 레포의 담당 |
|---|---|
| [오인성](https://github.com/ois0886) | 추천 서버·데이터·알고리즘·평가 |

[소스 출처](docs/PROVENANCE.md)
프로젝트에는 별도 담당자의 모바일 앱도 포함되며, 이 레포는 공통 API 연동 범위를 다룹니다.
