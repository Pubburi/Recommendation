"""Run an authored B1 fit/transform demonstration, not a real-catalog quality evaluation."""

import argparse
import json
import sys
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from pubburi_recommendation.baseline import (
    CatalogProduct,
    Constraints,
    ContractModel,
    ProductId,
    RecommendationRequest,
    recommend_baseline,
)
from pubburi_recommendation.catalog_audit import AuditError, read_json
from pubburi_recommendation.content_model import (
    ContentProduct,
    ContentProfile,
    FittedContentModel,
    GroupId,
    validate_catalog,
)
from pubburi_recommendation.scenario_evaluation import eligibility_issues


class ContentCase(ContractModel):
    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    candidate_ids: list[ProductId] = Field(max_length=1000)
    profile: ContentProfile = Field(default_factory=ContentProfile)
    reference_product_id: ProductId | None = None
    constraints: Constraints = Field(default_factory=Constraints)
    limit: int = Field(default=12, ge=1, le=100)
    expected_eligible_ids: list[ProductId] = Field(max_length=1000)
    fact_basis: str = Field(min_length=1, max_length=1000)


class ContentExperiment(ContractModel):
    schema_version: Literal[1]
    experiment_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,99}$")
    # Real source audit/import is separate; an unreviewed source cannot silently become safe.
    data_kind: Literal["authored_model_fixture"]
    catalog_version: str = Field(min_length=1, max_length=100)
    catalog: list[ContentProduct] = Field(min_length=1, max_length=1000)
    fit_group_ids: list[GroupId] = Field(min_length=1, max_length=1000)
    transform_group_ids: list[GroupId] = Field(min_length=1, max_length=1000)
    cases: list[ContentCase] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_partition_and_facts(self) -> Self:
        validate_catalog(self.catalog)
        fit, transform = set(self.fit_group_ids), set(self.transform_group_ids)
        if len(fit) != len(self.fit_group_ids) or len(transform) != len(self.transform_group_ids):
            raise ValueError("partition_groups_must_be_unique")
        if fit & transform:
            raise ValueError("sku_groups_must_not_cross_fit_transform")
        if fit | transform != {product.sku_group for product in self.catalog}:
            raise ValueError("partition_must_cover_exact_catalog_groups")
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("case_ids_must_be_unique")
        products = {product.product_id: product for product in self.catalog}
        for case in self.cases:
            if len(set(case.candidate_ids)) != len(case.candidate_ids):
                raise ValueError("candidate_ids_must_be_unique")
            if not set(case.candidate_ids) <= products.keys():
                raise ValueError("unknown_candidate_id")
            if any(products[pid].sku_group not in transform for pid in case.candidate_ids):
                raise ValueError("demo_candidates_must_be_in_transform_partition")
            if case.reference_product_id is not None:
                if case.reference_product_id not in products:
                    raise ValueError("unknown_reference_product")
                if case.profile != ContentProfile():
                    raise ValueError("choose_reference_or_explicit_profile")
            expected = case.expected_eligible_ids
            if len(set(expected)) != len(expected) or not set(expected) <= set(case.candidate_ids):
                raise ValueError("expected_ids_must_be_unique_candidates")
            for pid in case.candidate_ids:
                valid = not eligibility_issues(products[pid], case.constraints)
                valid = valid and pid != case.reference_product_id
                if valid != (pid in expected):
                    raise ValueError("manual_eligibility_conflicts_with_catalog_facts")
        return self


def run_experiment(spec: ContentExperiment, spec_sha256: str) -> dict:
    training = [product for product in spec.catalog if product.sku_group in spec.fit_group_ids]
    model = FittedContentModel.fit(training)
    products = {product.product_id: product for product in spec.catalog}
    cases = []
    for case in spec.cases:
        candidates = [products[pid] for pid in case.candidate_ids]
        constraints = case.constraints
        if case.reference_product_id is None:
            result = model.rank(candidates, case.profile, constraints, limit=case.limit)
        else:
            result = model.similar(
                products[case.reference_product_id], candidates, constraints, limit=case.limit
            )
            constraints = Constraints.model_validate(
                {
                    **constraints.model_dump(),
                    "exclude_product_ids": sorted(
                        set(constraints.exclude_product_ids) | {case.reference_product_id}
                    ),
                }
            )
        # Independently declared facts/requirements, never B1 scores, determine correctness here.
        ids = [item.product_id for item in result.items]
        issues = []
        if len(set(ids)) != len(ids):
            issues.append("duplicate_result")
        if not set(ids) <= set(case.expected_eligible_ids):
            issues.append("ineligible_result")
        if result.eligible_count != len(case.expected_eligible_ids):
            issues.append("eligible_count_mismatch")
        if len(ids) != min(case.limit, len(case.expected_eligible_ids)):
            issues.append("result_count_mismatch")
        baseline_catalog = [
            CatalogProduct.model_validate(
                {name: getattr(product, name) for name in CatalogProduct.model_fields}
            )
            for product in candidates
        ]
        baseline = recommend_baseline(
            RecommendationRequest(
                catalog=baseline_catalog, constraints=constraints, limit=case.limit
            )
        )
        cases.append(
            {
                "case_id": case.case_id,
                "passed_contract": not issues,
                "issues": issues,
                "b0_product_ids": [item.product_id for item in baseline.items],
                "b1": result.model_dump(mode="json"),
            }
        )
    return {
        "schema_version": 1,
        "experiment_id": spec.experiment_id,
        "spec_sha256": spec_sha256,
        "data_kind": spec.data_kind,
        "catalog_version": spec.catalog_version,
        "model_fingerprint": model.fingerprint,
        "fit_summary": model.summary,
        "transform_products": len(spec.catalog) - len(training),
        "transform_groups": len(spec.transform_group_ids),
        "case_count": len(cases),
        "passed_contract_cases": sum(case["passed_contract"] for case in cases),
        "passed_contract": all(case["passed_contract"] for case in cases),
        "ranking_metrics": {"status": "not_calculated", "reason": "no_relevance_judgments"},
        "limitations": [
            "actual_fit_on_authored_fixture_only_not_reviewed_service_skus",
            "group_split_regression_not_new_product_quality_or_final_holdout",
            "b0_b1_order_difference_not_quality_improvement",
            "no_user_preference_learning_or_performance_claim",
        ],
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if not {".pubburi", "reports"} & set(args.output.resolve().parts):
            raise AuditError("report_requires_private_or_reports_directory")
        if args.output.exists():
            raise AuditError("existing_report_must_be_preserved")
        payload, sha256 = read_json(args.spec)
        report = run_experiment(ContentExperiment.model_validate(payload), sha256)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as output:
            output.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(
            json.dumps(
                {
                    key: report[key]
                    for key in ("case_count", "passed_contract_cases", "passed_contract")
                }
            )
        )
        return 0 if report["passed_contract"] else 1
    except (OSError, ValueError, TypeError, KeyError) as error:
        reason = str(error) if isinstance(error, AuditError) else type(error).__name__
        print(f"Content experiment failed: {reason}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
