# Recommendation working guide

Use Python3.12, FastAPI and fixed uv; commit uv.lock and install with --locked.
The current data/model/delivery plan is [DATA-AND-MODEL-PLAN](docs/DATA-AND-MODEL-PLAN.md).
Backend owns business data/accounts/search; Recommendation owns source rights, curation, models and
independent evaluation. Keep changes inside the delegated repo and respect the single Git writer/lease.
The coordinator owns shared runtime/DB/API decisions, Notion, final merge and cleanup. Follow the brief
[Backend operating rules](https://github.com/Pubburi/Backend/blob/main/AGENTS.md); do not copy them here.

## Runtime and data contracts

- Preserve health and the seven POST contracts: B0 baseline; B1 content/exploration/similar/context/
  feedback; model-free search-phrases. Their API docs are authoritative. Startup/health/B0 need no DB,
  numerical import, model download or network. B1 fits only the explicit request catalog, once per request.
- All POSTs retain512KiB cumulative bodies and10-second total receive deadlines. Duplicate decoded JSON
  keys are rejected only after successful full decode; preserve syntax/encoding/depth error priority.
  This receive bound does not cancel or bound a running CPU fit.
- Preserve hard/negative/ID/group exclusions, actual positive contributions and deterministic fallback.
  No zero-fill in informative-positive mode; no reference/quantity popularity inference. Unknown facts
  are not zero/empty tags. Reference evidence is not a user preference or whole-cart compatibility.
- Opt-in explanations/preferences preserve default/false wire, scores/order/fit. Keep actual/target/unit,
  winning source ID, active bounds and truncation explicit. Stored soft targets never become hard filters;
  reject conflicting/lossy inputs and retain raw Decimal precision and Backend literal authority.
- Follow [CONTENT-MODEL](docs/CONTENT-MODEL.md) and [EVALUATION](docs/EVALUATION.md): atomic tokens,
  observed numeric masks/scales, train-only vocabulary/transform and grouped leakage boundaries.
  Freeze independent facts before fit; production scoring/filter/format helpers never generate gold.
  B0 order, DEMO/fixture checks and shared-feature facts are not user-quality or holdout evidence.
- Source rights/manifests/revisions and accepted receipts must match before use. Keep raw/model/logs and
  actual business responses ignored. Never infer rights or business IDs from names/URLs/sourceName.
  No failed-source retry/threshold or rate-limit bypass, accounts, external contacts/cost or AWS without
  existing authorization. Wikidata uses fixed HTTPS/single GET/maxlag5/10-ID/byte/timeout gates.
- Source quantity units require exact supported Wikidata entity URIs. Explicit metadata/identity/type
  contradictions, active ambiguous relations and malformed P31 remain held/unknown before fit or curation;
  deprecated statements stay ignored. Labels retain ko/en/mul precedence and original language.
  GTIN checksum/string is not assignment, packaging or sale authority; preserve shared-ID collision holds.
- Follow [SOURCE-CATALOG](docs/SOURCE-CATALOG.md), [BUSINESS-EXPORT](docs/BUSINESS-EXPORT.md) and
  [FAMILY-BROWSE-DEMO](docs/FAMILY-BROWSE-DEMO.md): reviewed scope, exact quantities/unknown, explicit
  one-to-one business IDs/groups/full-response hashes, original capture/freshness and origin separation.
  Keep container gates; family null volume is allowed only in its owned browse DEMO scope. DEMO prices
  are not sale observations. No mapping means no export; family/source IDs never automatically become SKUs.
- Keep [checked export](docs/CHECKED-EXPORT-ACCEPTANCE.md) and
  [Backend bundle](docs/BACKEND-CATALOG-BUNDLE.md) authority/bytes/completion gates. Revalidate original
  artifacts/inputs, preserve old outputs, distinguish fresh from historical replay and completed from passed.
  Backend owns current business/account revalidation; pinning is not a signature or service/quality approval.

## Delivery and validation

- All R01–R08/F01–F12 (20 MVP functions) require implementation, integration and necessary acceptance by
  2026-12-31 Asia/Seoul. Keep the11-22 local/DB contract and12-13 P1 target. Actual permitted catalog/
  mapping/B1 fit/B0/factual constraints/leakage/fallback/reproducibility belong before the MVP deadline.
  Provider/fixture-only work never completes a whole feature. Do not wait for external users/future logs.
- Required unfinished work remains first, even after a missed deadline; report it without extending it.
  Additional models/tuning/optimization/portfolio work begins from2027-01-01 only after MVP acceptance.
  Final deadline is2027-02-05 inclusive; no implementation/commits/merges from2027-02-06 00:00 KST.
  Chatbot/mobile implementation, real payment/shipping and AWS resources remain outside scope.
- Resume this chat every4hours with gpt-6.1-sol/ultra. Read current context/ownership/Git/PR status and
  relevant contracts, then do required product work or actual blocking defects. Do not create filler work.
- Run [TESTING](docs/TESTING.md)'s ./scripts/check.sh: locked pytest/Ruff and fresh distribution/runtime
  checks. Required CI, completed latest-head Codex review, relevant validation and no unresolved findings
  precede squash merge. Pending/failed review is not approval. Reply to fixes in Korean before native
  resolution without duplicates. Confirm main CI/ff-only sync and delete only fully merged branches.

## Minimal records and PRs

- Update an existing canonical contract/current plan when behavior or acceptance changes. Do not create
  per-run plans, test lists, experiment diaries or repeated status/README-comparison paragraphs.
  Review/check evidence belongs in open PR/CI; keep only one ignored work record and final handoff.
- Never add/edit comments, bodies, assignees or labels on closed/merged PRs. Keep detailed work/discussion
  in existing GitHub Project/Discussion and only TODO/done in Notion; create no unnecessary records.
- Keep a separate measurement only for independent actual before/after values, interpretation and limits
  that are needed beyond the PR; merge overlaps. Retain source/license and model-adoption decisions.
  Remove rejected one-off experiments from runtime/dedicated tests, preserving their measurement and exact
  historical code/lockfile links. Do not delete useful integrity/security or core independent checks.
- Use Korean Conventional Commit/PR titles and one reviewable purpose per commit, following
  [CONTRIBUTING](CONTRIBUTING.md). No WIP/empty commits, forced history rewriting or unrelated changes.
- README currently has three supported cases and one missing toward the final four. Change the register
  only when selection/evidence changes; preserve concrete code/measurement or fixed Git links. Never split
  adjacent fixes/bootstrap topics to fill the count or invent failures/contribution/quality/performance.
  Performance requires real comparable measurements. Do not restore project/role/provenance link tables,
  successor narration or screenshot sections in this repo.

## README 대표 사례 검토

대표 사례는 주기적으로 검토하며 **문제 → 원인 → 해결 → 결과 → 대체안/회고 → 코드** 순서를 유지한다. 실제 오류 개선·최적화의 원인/대안·전후 실측과 한계, 현재 핵심 코드로 설명할 수 있는 소재를 우선한다. 기존 사례보다 채용 관점에서 더 설득력 있는 근거를 확보했을 때만 해당 사례를 교체하고 나머지 내용/순서는 보존한다. 최신 작업·코드량·테스트/CI 수만으로 교체하거나 없는 성능/기여를 만들지 않는다. 코드는 현재 소스의 핵심 분기·데이터 경계만 짧은 연속 발췌로 펼쳐 보이며, README 문제/원인/해결/결과/대체안·회고/코드에는 하이퍼링크를 두지 않고 근거 링크는 기존 case-study-register/정본문서에서 관리하며, 임의 stub·생략기호·전체 코드 부록은 만들지 않는다. 비교는 계속하되 변경 없는 매회 유지 보고서는 만들지 않는다.
