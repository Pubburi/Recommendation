"""Check frozen, authored contract scenarios without invoking the recommendation engine."""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import ConfigDict, Field, ValidationError, model_validator

# Reuse wire types only. Production ranking/filter/reason helpers are never called.
from pubburi_recommendation.baseline import (
    CatalogProduct,
    Constraints,
    ContractModel,
    ProductId,
    RecommendationRequest,
    RecommendationResponse,
)
from pubburi_recommendation.catalog_audit import AuditError, read_json


class EvaluationInputError(ValueError):
    """Safe diagnostic, without request/response contents or local file paths."""


def eligibility_issues(product: CatalogProduct, constraints: Constraints) -> list[str]:
    """An independent requirements checker, not the production eligibility implementation."""
    issues = []
    if product.available is not True:
        issues.append("unavailable")
    if product.product_id in constraints.exclude_product_ids:
        issues.append("excluded_product")
    if constraints.categories and product.category not in constraints.categories:
        issues.append("category_mismatch")
    for attribute, minimum, maximum, prefix in (
        (product.price_krw, constraints.min_price_krw, constraints.max_price_krw, "price"),
        (product.abv_percent, constraints.min_abv_percent, constraints.max_abv_percent, "abv"),
    ):
        if minimum is None and maximum is None:
            continue
        if attribute is None:
            issues.append(f"{prefix}_unknown")
            continue
        if minimum is not None and attribute < minimum:
            issues.append(f"{prefix}_below_min")
        if maximum is not None and attribute > maximum:
            issues.append(f"{prefix}_above_max")
    return issues


class Scenario(ContractModel):
    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    purpose: str = Field(min_length=1, max_length=300)
    candidate_ids: list[ProductId] = Field(max_length=1000)
    constraints: Constraints = Field(default_factory=Constraints)
    limit: int = Field(default=12, ge=1, le=100)
    expected_eligible_ids: list[ProductId] = Field(max_length=1000)
    expected_item_ids: list[ProductId] | None = Field(default=None, max_length=100)
    expected_item_count: int | None = Field(default=None, ge=0, le=100)
    fact_basis: str = Field(min_length=1, max_length=1000)


class ScenarioSuite(ContractModel):
    schema_version: Literal[1]
    suite_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,99}$")
    data_kind: Literal["authored_contract_fixture"]
    catalog_version: str = Field(min_length=1, max_length=100)
    algorithm: str = Field(min_length=1, max_length=100)
    ordering_policy: Literal["b0_id_ascending", "constraints_only"] = "b0_id_ascending"
    catalog: list[CatalogProduct] = Field(max_length=1000)
    scenarios: list[Scenario] = Field(min_length=1, max_length=1000)

    def request_for(self, scenario: Scenario) -> RecommendationRequest:
        products = {product.product_id: product for product in self.catalog}
        return RecommendationRequest(
            catalog=[products[pid] for pid in scenario.candidate_ids],
            constraints=scenario.constraints,
            limit=scenario.limit,
        )

    @model_validator(mode="after")
    def validate_declared_facts(self) -> Self:
        if self.ordering_policy == "b0_id_ascending" and self.algorithm != "b0-id-ascending-v1":
            raise ValueError("b0_order_policy_requires_b0_algorithm")
        products = {product.product_id: product for product in self.catalog}
        if len(products) != len(self.catalog):
            raise ValueError("suite_catalog_ids_must_be_unique")
        if len({scenario.case_id for scenario in self.scenarios}) != len(self.scenarios):
            raise ValueError("scenario_ids_must_be_unique")
        for scenario in self.scenarios:
            candidates = scenario.candidate_ids
            expected = scenario.expected_eligible_ids
            if len(set(candidates)) != len(candidates) or not set(candidates) <= products.keys():
                raise ValueError("scenario_candidates_must_be_unique_known_ids")
            if len(set(expected)) != len(expected) or not set(expected) <= set(candidates):
                raise ValueError("expected_ids_must_be_unique_candidates")
            # Manual declarations are checked against request facts, never filled by a model.
            for pid in candidates:
                eligible = not eligibility_issues(products[pid], scenario.constraints)
                if eligible != (pid in expected):
                    raise ValueError("declared_eligibility_conflicts_with_catalog_facts")
            if self.ordering_policy == "b0_id_ascending":
                if scenario.expected_item_ids != sorted(expected)[: scenario.limit]:
                    raise ValueError("declared_b0_order_or_limit_is_inconsistent")
                if scenario.expected_item_count is not None:
                    raise ValueError("b0_count_is_part_of_declared_order")
            else:
                if scenario.expected_item_ids is not None:
                    raise ValueError("constraints_only_has_no_order_judgments")
                if scenario.expected_item_count is not None and scenario.expected_item_count > min(
                    len(expected), scenario.limit
                ):
                    raise ValueError("declared_count_exceeds_eligible_limit")
        return self


class CapturedResponse(ContractModel):
    case_id: str = Field(min_length=1, max_length=100)
    status_code: int = Field(ge=100, le=599)
    body: Any


class ResponseBundle(ContractModel):
    schema_version: Literal[1]
    suite_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    algorithm: str = Field(min_length=1, max_length=100)
    responses: list[CapturedResponse] = Field(max_length=1000)


class CandidateEnvelopeItem(ContractModel):
    # Model-specific scores/explanations are intentionally outside this minimal check.
    model_config = ConfigDict(strict=True, extra="ignore")
    product_id: ProductId
    reasons: list[str] = Field(max_length=32)


class CandidateEnvelope(ContractModel):
    model_config = ConfigDict(strict=True, extra="ignore")
    algorithm: str = Field(min_length=1, max_length=100)
    items: list[CandidateEnvelopeItem] = Field(max_length=1000)
    eligible_count: int = Field(ge=0)
    fallback_reason: str | None = Field(default=None, max_length=100)


def expected_reasons(constraints: Constraints, *, baseline: bool) -> set[str]:
    reasons = {"available"}
    if baseline:
        reasons.add("deterministic_baseline")
    if constraints.categories:
        reasons.add("category_match")
    for minimum, maximum, code in (
        (constraints.min_price_krw, constraints.max_price_krw, "price_within_range"),
        (constraints.min_abv_percent, constraints.max_abv_percent, "abv_within_range"),
    ):
        if (minimum, maximum) != (None, None):
            reasons.add(code)
    return reasons


def check_response(suite: ScenarioSuite, scenario: Scenario, captured: CapturedResponse) -> dict:
    issues = []
    baseline = suite.ordering_policy == "b0_id_ascending"
    if captured.status_code != 200:
        return {
            "case_id": scenario.case_id,
            "passed": False,
            "checked_items": 0,
            "issues": ["unexpected_http_status"],
        }
    try:
        response = (RecommendationResponse if baseline else CandidateEnvelope).model_validate(
            captured.body
        )
    except ValidationError:
        return {
            "case_id": scenario.case_id,
            "passed": False,
            "checked_items": 0,
            "issues": ["response_schema_invalid"],
        }
    products = {product.product_id: product for product in suite.request_for(scenario).catalog}
    if response.algorithm != suite.algorithm:
        issues.append("response_algorithm_mismatch")
    actual_ids = [item.product_id for item in response.items]
    if len(set(actual_ids)) != len(actual_ids):
        issues.append("duplicate_product")
    if len(actual_ids) > scenario.limit:
        issues.append("limit_exceeded")
    if baseline and actual_ids != sorted(actual_ids):
        issues.append("b0_order_mismatch")
    if baseline and actual_ids != scenario.expected_item_ids:
        issues.append("declared_items_mismatch")
    if (
        not baseline
        and scenario.expected_item_count is not None
        and len(actual_ids) != scenario.expected_item_count
    ):
        issues.append("declared_count_mismatch")
    for item in response.items:
        if item.product_id not in products:
            issues.append("unknown_candidate")
        else:
            issues.extend(eligibility_issues(products[item.product_id], scenario.constraints))
        if len(set(item.reasons)) != len(item.reasons):
            issues.append("duplicate_reason")
        expected_codes = expected_reasons(scenario.constraints, baseline=baseline)
        if baseline and set(item.reasons) != expected_codes:
            issues.append("reason_mismatch")
        if not baseline:
            if not expected_codes <= set(item.reasons):
                issues.append("required_constraint_reason_missing")
            hard_codes = {"available", "category_match", "price_within_range", "abv_within_range"}
            if set(item.reasons) & hard_codes != expected_codes:
                issues.append("inactive_constraint_reason")
    if response.eligible_count != len(scenario.expected_eligible_ids):
        issues.append("eligible_count_mismatch")
    expected_fallback = None if scenario.expected_eligible_ids else "no_eligible_products"
    if response.fallback_reason != expected_fallback:
        issues.append("fallback_reason_mismatch")
    return {
        "case_id": scenario.case_id,
        "passed": not issues,
        "checked_items": len(actual_ids),
        "issues": sorted(set(issues)),
    }


def evaluate(suite: ScenarioSuite, bundle: ResponseBundle, suite_sha256: str) -> dict:
    if bundle.suite_sha256 != suite_sha256:
        raise EvaluationInputError("suite_snapshot_hash_mismatch")
    if bundle.algorithm != suite.algorithm:
        raise EvaluationInputError("bundle_algorithm_mismatch")
    grouped = defaultdict(list)
    for response in bundle.responses:
        grouped[response.case_id].append(response)
    results = []
    for scenario in suite.scenarios:
        responses = grouped[scenario.case_id]
        if len(responses) != 1:
            results.append(
                {
                    "case_id": scenario.case_id,
                    "passed": False,
                    "checked_items": 0,
                    "issues": ["missing_response" if not responses else "duplicate_response"],
                }
            )
        else:
            results.append(check_response(suite, scenario, responses[0]))
    known = {scenario.case_id for scenario in suite.scenarios}
    global_issues = ["unexpected_case_response"] if set(grouped) - known else []
    passed = sum(result["passed"] for result in results)
    return {
        "schema_version": 1,
        "suite_id": suite.suite_id,
        "suite_sha256": suite_sha256,
        "catalog_version": suite.catalog_version,
        "algorithm": suite.algorithm,
        "ordering_policy": suite.ordering_policy,
        "response_contract_scope": "b0_wire"
        if suite.ordering_policy == "b0_id_ascending"
        else "minimal_candidate_envelope_only",
        "reason_check_scope": "exact_b0_filter_codes"
        if suite.ordering_policy == "b0_id_ascending"
        else "required_hard_constraint_codes_only",
        "cardinality_check_scope": "declared_b0_items"
        if suite.ordering_policy == "b0_id_ascending"
        else "only_cases_with_explicit_expected_item_count",
        "data_kind": suite.data_kind,
        "scenario_count": len(results),
        "passed_cases": passed,
        "failed_cases": len(results) - passed,
        "passed": passed == len(results) and not global_issues,
        "global_issues": global_issues,
        "cases": results,
        "issue_case_counts": dict(
            sorted(Counter(issue for result in results for issue in result["issues"]).items())
        ),
        "ranking_metrics": {
            "status": "not_calculated",
            "reason": "no_independent_relevance_judgments",
        },
        "limitations": [
            "authored_contract_checks_not_user_preference_quality",
            "not_trained_model_evaluation_or_final_holdout",
            "model_scores_and_additional_explanations_not_checked",
            "no_latency_or_conversion_claim",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        suite_json, suite_hash = read_json(args.suite)
        responses_json, responses_hash = read_json(args.responses)
        suite = ScenarioSuite.model_validate(suite_json)
        bundle = ResponseBundle.model_validate(responses_json)
        report = evaluate(suite, bundle, suite_hash)
        report["responses_sha256"] = responses_hash
        if not {".pubburi", "reports"} & set(args.output.resolve().parts):
            raise EvaluationInputError("report_requires_private_or_reports_directory")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if args.output.exists():
            raise EvaluationInputError("existing_report_must_be_preserved")
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    key: report[key]
                    for key in ("passed", "scenario_count", "passed_cases", "failed_cases")
                }
            )
        )
        return 0 if report["passed"] else 1
    except (OSError, ValueError, TypeError, KeyError) as error:
        reason = (
            str(error)
            if isinstance(error, (EvaluationInputError, AuditError))
            else type(error).__name__
        )
        print(f"Scenario evaluation failed: {reason}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
