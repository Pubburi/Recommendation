#!/usr/bin/env python3
"""Actually fit the authored B1 fixture and retain only a safe contract summary for CI."""

import json
from pathlib import Path

from pubburi_recommendation.catalog_audit import read_json
from pubburi_recommendation.content_experiment import ContentExperiment, run_experiment

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    payload, sha256 = read_json(ROOT / "evaluation/content-fit-v1.json")
    report = run_experiment(ContentExperiment.model_validate(payload), sha256)
    # No raw products, vocabulary/IDF, learned artifacts or original responses in CI artifacts.
    summary = {key: value for key, value in report.items() if key != "cases"}
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "content-fit-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Authored B1 fit: {report['passed_contract_cases']}/{report['case_count']} "
        "contract cases. "
        "Not a real-catalog relevance evaluation."
    )
    if not report["passed_contract"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
