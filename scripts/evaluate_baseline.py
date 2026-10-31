#!/usr/bin/env python3
"""Run the authored scenario suite through the HTTP app and its independent checker."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from pubburi_recommendation.catalog_audit import read_json
from pubburi_recommendation.main import app
from pubburi_recommendation.scenario_evaluation import ResponseBundle, ScenarioSuite, evaluate

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=ROOT / "evaluation/baseline-contract-v1.json")
    args = parser.parse_args()
    suite_json, suite_hash = read_json(args.suite)
    suite = ScenarioSuite.model_validate(suite_json)
    if suite.algorithm != "b0-id-ascending-v1" or suite.ordering_policy != "b0_id_ascending":
        raise ValueError("This HTTP runner only captures the implemented B0 API")
    responses = []
    with TestClient(app) as client:
        for scenario in suite.scenarios:
            response = client.post(
                "/v1/recommendations/baseline", json=suite.request_for(scenario).model_dump()
            )
            try:
                body = response.json()
            except ValueError:
                body = None
            responses.append(
                {"case_id": scenario.case_id, "status_code": response.status_code, "body": body}
            )
    bundle = ResponseBundle(
        schema_version=1, suite_sha256=suite_hash, algorithm=suite.algorithm, responses=responses
    )
    capture = json.dumps(bundle.model_dump(), ensure_ascii=False, indent=2) + "\n"
    report = evaluate(suite, bundle, suite_hash)
    report["responses_sha256"] = hashlib.sha256(capture.encode()).hexdigest()
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "baseline-responses.json").write_text(capture, encoding="utf-8")
    (reports / "baseline-scenarios.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Authored contract scenarios: {report['passed_cases']}/{report['scenario_count']} passed."
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"Baseline scenario capture failed: {type(error).__name__}", file=sys.stderr)
        raise SystemExit(2) from None
