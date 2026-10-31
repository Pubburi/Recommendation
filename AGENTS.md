# Recommendation working guide

- Use Python 3.12, FastAPI and uv. Commit uv.lock; sync with --locked.
- Current contracts are GET /health and POST /v1/recommendations/baseline (untrained B0). Follow docs/BASELINE-API.md. No catalog/model is loaded or persisted; do not imply B1 learning or Backend integration is complete.
- Keep initialization free of database, model download and external API requirements.
- Validate with ./scripts/check.sh (pytest, Ruff and distribution build).
- Implement data preparation, content-based recommendations, fallbacks and model evaluation under the approved roadmap; never present unfinished features as implemented.
- Do not commit datasets, model weights, .venv/, credentials or generated distributions.
- Use PRs and Conventional Commits. Mobile implementation is separately owned.

## 커밋·PR 작성

- [협업 규칙](CONTRIBUTING.md)에 따라 `feat:`, `fix:`, `test:`, `ci:`, `docs:` 등의 영어 유형과 한국어 제목·필요한 본문을 사용한다. 식별자·제품 이름은 원문을 유지할 수 있다.
- 한 커밋은 한 가지 검토 가능한 목적을 담고 필요한 구현·테스트·문서를 함께 묶는다. 무관한 모델/데이터·리팩터링·의존성 변경은 분리하며 각 커밋을 빌드·검증 가능한 상태로 유지한다. WIP·빈 커밋·파일별 억지 분할은 하지 않는다.
- PR 제목과 최종 Squash 제목도 한국어 Conventional Commit 형식으로, 필요한 Squash 본문도 한국어로 작성한다. 기존 Squash 방식을 유지하며 main의 독립 변경 단위는 PR부터 나눈다. 과거 병합 이력은 재작성하지 않는다.

## Delivery and automation

- Follow this repo's docs/DATA-AND-MODEL-PLAN.md and the latest approved planning in this chat/private context as the canonical recommendation delivery plan. Own data sources, collection/cleaning, catalog/features, models, training/evaluation, experiments and related design/tests here. Backend owns its business database, authentication/product APIs and search/index integration; its delivery docs are integration references rather than the recommendation plan. Deadline: 2027-02-05 inclusive Asia/Seoul; no new implementation, commits or merges from 2027-02-06 00:00.
- All R01–R08 and F01–F12 are required; P1/P2 determines order only. Keep chatbot, mobile implementation, real payments/shipping and AWS resource creation outside this work. AWS requires a later user instruction.
- Resume the current chat every two hours. Read latest planning, docs/plans, Git, PR reviews and CI. Prefer finishing verifiable product work over repeated audits.
- Check active task ownership and acquire this repo's ignored .pubburi/automation-lease using Backend/scripts/automation_lease.py. Never steal a live lease or overwrite user work. Preserve .pubburi/ and private context; never commit or print their sensitive contents.
- Automated PRs require successful required CI, completed Codex review of the latest head, relevant manual validation and no unresolved findings before squash merge. Pending/failed/quota-limited review is not approval. Request review and reply to fixed findings in Korean with commit and validation evidence before native resolution; avoid duplicate replies.
- Confirm merge and main CI, ff-only sync and remove only fully merged branches without extra work. Do not relax existing protection.
- Record only observed completion and reproducible measurements. Keep private paths, credentials and private planning URLs out of new public evidence.
- README describes current functionality. Do not add successor-project narration or invented results. Backend/Recommendation need no screenshot section; Frontend uses verified real screens only.

## Review guidelines

- Write review findings in Korean. Focus on concrete correctness, ownership, data preservation and API compatibility issues introduced by the diff.
- Do not treat future roadmap items as implemented or require out-of-scope product features in documentation/setup PRs.

## Role agents, case studies and continuous improvement

- Use coordinator + Backend/Frontend/Recommendation workers in this same chat on each scheduled run. See Backend/docs/AUTOMATION-PLAYBOOK.md (sibling checkout or GitHub main). No separate user chats or duplicate schedules.
- Coordinator records atomic repository ownership and delegated files/Git owner. One writer per repo/file; no concurrent staging or branch changes. Workers stay inside their assigned repo. Coordinator owns shared API/ERD decisions, shared runtime integration, PR gates and the single Notion update. Internal worker coordination is allowed; messaging other user chats or external people is not.
- Final README target is exactly four real, independently justified hiring-relevant problem-solving cases. Order: 문제 → 원인 → 해결 → 결과 → 대체안/회고 → 코드. Use substantial real code excerpts, displayed by default, and live source links.
- Never invent past failures, personal contribution, model results or performance. Do not split one bootstrap/CI topic into filler cases. If evidence is insufficient, record the actual count and concrete acquisition tasks in docs/case-study-register.md and planning; fill the four only after implementation/verification.
- On every run compare current cases with candidates from the work. Replace only when a genuinely stronger real problem-solving case is discovered for hiring reviewers, based on actual impact, state/async/data difficulty, cause evidence, alternatives, implementation contribution and reproducible outcomes. Replace stronger cases immediately, one or many; record why. No forced replacement; preserve cases when no better evidence exists. Do not select by novelty, code size, test totals or arbitrary scores.
- Keep regression evidence, test counts/lists and CI aggregation in plans/PR/CI rather than README. Performance requires real comparable before/after measurements; correctness counts, audit reductions and CI time are not application performance.
- Do not restore the README related-project/developer section, repository/responsibility or developer tables, planning/collaboration/provenance link collections, mobile-role narration or their ToC/anchors. Preserve source provenance documents themselves. Backend/Recommendation need no screenshots; Frontend uses verified real completed screens only.
- After actionable planning tasks finish, each worker continues reproducing and fixing existing-project defects and measured optimization opportunities until the deadline. Coordinator adds deduplicated evidence-based tasks with owner, impact, priority and acceptance criteria. Do not stop at monitoring, expand commercial scope, invent issues or churn empty changes. Keep all existing CI/latest-review/manual-validation/merge/branch-cleanup and cost/account approval rules.
