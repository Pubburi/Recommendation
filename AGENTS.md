# Recommendation working guide

- Use Python 3.12, FastAPI and uv. Commit uv.lock; sync with --locked.
- Current public contract is GET /health only. Do not imply a trained model exists.
- Keep initialization free of database, model download and external API requirements.
- Validate with ./scripts/check.sh (pytest, Ruff and distribution build).
- Implement data preparation, content-based recommendations, fallbacks and model evaluation under the approved roadmap; never present unfinished features as implemented.
- Do not commit datasets, model weights, .venv/, credentials or generated distributions.
- Use PRs and Conventional Commits. Mobile implementation is separately owned.

## Delivery and automation

- Follow the approved delivery contract in Backend docs/DELIVERY-PLAN.md (the sibling checkout or its GitHub main). Deadline: 2027-02-05 inclusive Asia/Seoul; no new implementation, commits or merges from 2027-02-06 00:00.
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
