"""Fit the existing B1 on explicitly mapped demo facts and compare frozen contract scenarios."""

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from pubburi_recommendation.baseline import (
    Abv,
    Category,
    Constraints,
    ContractModel,
    Price,
    RecommendationRequest,
    RecommendationResponse,
    recommend_baseline,
)
from pubburi_recommendation.business_export import (
    ReviewedMapping,
    build_exports,
    content_hash,
    utc_time,
)
from pubburi_recommendation.catalog_audit import AuditError, read_json
from pubburi_recommendation.content_api import ContentRecommendationRequest
from pubburi_recommendation.content_contracts import ContentProfile, ContentResponse, Tag, Volume
from pubburi_recommendation.package_identity_audit import Hash
from pubburi_recommendation.scenario_evaluation import eligibility_issues, expected_reasons
from pubburi_recommendation.source_catalog import Key, Note, load_source_catalog
from pubburi_recommendation.wikidata_collect import write_receipt


class FrozenFacts(ContractModel):
    available: bool
    category: Category | None
    price_krw: Price | None
    abv_percent: Abv | None
    volume_ml: Volume | None
    sku_group: Key
    taste_tags: list[Tag] | None = Field(max_length=20)
    aroma_tags: list[Tag] | None = Field(max_length=20)


class FrozenCase(ContractModel):
    case_id: Key
    profile: ContentProfile = Field(default_factory=ContentProfile)
    constraints: Constraints = Field(default_factory=Constraints)
    exclude_keys: list[Key] = Field(default_factory=list, max_length=1000)
    expected_eligible_keys: list[Key] = Field(max_length=1000)
    expected_item_count: int = Field(ge=0, le=100)
    expected_b1_fallback: (
        Literal["no_supported_preferences", "no_eligible_products", "no_matching_features"] | None
    )
    fact_basis: Note
    limit: int = Field(default=12, ge=1, le=100)


class ReviewedFitSpec(ContractModel):
    schema_version: Literal[1]
    experiment_id: Key
    evidence_kind: Literal["reviewed_public_source", "authored_regression_fixture"]
    source_catalog_sha256: Hash
    frozen_at_utc: str = Field(min_length=20, max_length=40)
    expected_facts: dict[Key, FrozenFacts] = Field(min_length=1, max_length=1000)
    scenarios: list[FrozenCase] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def frozen_references(self):
        utc_time(self.frozen_at_utc)
        if len({case.case_id for case in self.scenarios}) != len(self.scenarios):
            raise ValueError("scenario_ids_must_be_unique")
        for case in self.scenarios:
            if case.constraints.exclude_product_ids:
                raise ValueError("use_explicit_mapping_keys_not_unbound_business_ids")
            for keys in (case.exclude_keys, case.expected_eligible_keys):
                if len(keys) != len(set(keys)) or not set(keys) <= set(self.expected_facts):
                    raise ValueError("scenario_keys_must_be_unique_known_facts")
            if case.expected_item_count != min(case.limit, len(case.expected_eligible_keys)):
                raise ValueError("declared_count_must_match_current_candidate_contract")
        return self


def check_case(case, products, constraints, expected_ids, b0_data, b1_data):
    """Inspect frozen facts/results without calling any production scorer or filter."""
    baseline = RecommendationResponse.model_validate(b0_data)
    content = ContentResponse.model_validate(b1_data)
    issues = []
    by_id = {row.product_id: row for row in products}
    independently_eligible = {
        row.product_id for row in products if not eligibility_issues(row, constraints)
    }
    if independently_eligible != set(expected_ids):
        issues.append("frozen_eligibility_conflicts_with_facts")
    for name, response in (("b0", baseline), ("b1", content)):
        ids = [row.product_id for row in response.items]
        if len(ids) != len(set(ids)) or not set(ids) <= set(expected_ids):
            issues.append(name + "_duplicate_or_ineligible_item")
        if response.eligible_count != len(expected_ids):
            issues.append(name + "_eligible_count")
        if len(ids) != case.expected_item_count or len(ids) > case.limit:
            issues.append(name + "_item_count")
        for item in response.items:
            codes = expected_reasons(constraints, baseline=name == "b0")
            if not codes <= set(item.reasons) or len(item.reasons) != len(set(item.reasons)):
                issues.append(name + "_constraint_reasons")
            if name == "b0" and set(item.reasons) != codes:
                issues.append("b0_inactive_reason")
            hard_codes = {"available", "category_match", "price_within_range", "abv_within_range"}
            if name == "b1" and set(item.reasons) & hard_codes != codes:
                issues.append("b1_inactive_constraint_reason")
    if [row.product_id for row in baseline.items] != sorted(expected_ids)[: case.limit]:
        issues.append("b0_declared_order")
    if baseline.fallback_reason != (None if expected_ids else "no_eligible_products"):
        issues.append("b0_declared_fallback")
    if content.fallback_reason != case.expected_b1_fallback:
        issues.append("b1_declared_fallback")
    for item in content.items:
        if content.fallback_reason == "no_supported_preferences" and (
            item.score or item.contributions
        ):
            issues.append("b1_unsupported_fallback_score")
        if not math.isclose(
            item.score, sum(row.contribution for row in item.contributions), abs_tol=1e-9
        ):
            issues.append("b1_contribution_sum")
        product = by_id.get(item.product_id)
        if product is None:
            continue
        for contribution in item.contributions:
            if contribution.component == "text":
                allowed = (
                    {"category:" + product.category} if product.category is not None else set()
                )
                allowed |= {"taste:" + tag for tag in product.taste_tags or []}
                allowed |= {"aroma:" + tag for tag in product.aroma_tags or []}
                requested = {"category:" + tag for tag in case.profile.categories}
                requested |= {"taste:" + tag for tag in case.profile.taste_tags}
                requested |= {"aroma:" + tag for tag in case.profile.aroma_tags}
                if contribution.feature not in allowed & requested:
                    issues.append("b1_unsupported_text_contribution")
            else:
                field = contribution.component
                preference = getattr(case.profile, "preferred_" + field)
                if getattr(product, field) is None or preference is None:
                    issues.append("b1_unsupported_numeric_contribution")
    return {
        "case_id": case.case_id,
        "passed": not issues,
        "issues": sorted(set(issues)),
        "b0": b0_data,
        "b1": b1_data,
    }


def run_reviewed_fit(spec, catalog, exports, mapping, export_report, now):
    if (
        spec.source_catalog_sha256 != content_hash(catalog)
        or spec.evidence_kind != catalog["evidence_kind"]
        or utc_time(spec.frozen_at_utc) > now
    ):
        raise AuditError("frozen_spec_source_or_time_mismatch")
    if not exports:
        raise AuditError("reviewed_mapped_catalog_required_for_actual_fit")
    content_request = ContentRecommendationRequest.model_validate(exports["b1-demo-request.json"])
    products = content_request.catalog
    ids = {row.catalog_record_id: row.backend_product_id for row in mapping.records}
    if set(spec.expected_facts) != set(ids):
        raise AuditError("frozen_facts_must_cover_exact_mapped_catalog")
    by_id = {row.product_id: row for row in products}
    for key, expected in spec.expected_facts.items():
        product = by_id[ids[key]]
        if any(getattr(product, name) != value for name, value in expected.model_dump().items()):
            raise AuditError("frozen_product_facts_conflict_before_fit")
    # Resolve only the already reviewed mapping; neither source IDs nor model scores infer labels.
    requests = []
    for case in spec.scenarios:
        constraints = Constraints.model_validate(
            {
                **case.constraints.model_dump(),
                "exclude_product_ids": [ids[key] for key in case.exclude_keys],
            }
        )
        expected = [ids[key] for key in case.expected_eligible_keys]
        actual = {row.product_id for row in products if not eligibility_issues(row, constraints)}
        if actual != set(expected):
            raise AuditError("frozen_scenario_conflicts_before_fit")
        requests.append((case, constraints, expected))
    from pubburi_recommendation.content_model import FittedContentModel

    model = FittedContentModel.fit(products)
    cases = []
    for case, constraints, expected in requests:
        baseline = recommend_baseline(
            RecommendationRequest(
                catalog=exports["b0-demo-request.json"]["catalog"],
                constraints=constraints,
                limit=case.limit,
            )
        )
        content = model.rank(products, case.profile, constraints, limit=case.limit)
        cases.append(
            check_case(
                case, products, constraints, expected, baseline.model_dump(), content.model_dump()
            )
        )
    return {
        "schema_version": 1,
        "experiment_id": spec.experiment_id,
        "evidence_kind": spec.evidence_kind,
        "fit_scope": "known_mapped_demo_catalog",
        "source_catalog_sha256": spec.source_catalog_sha256,
        "frozen_at_utc": spec.frozen_at_utc,
        "executed_at_utc": now.isoformat(),
        "snapshot_origin": export_report["snapshot_origin"],
        "model_fingerprint": model.fingerprint,
        "fit_summary": model.summary,
        "vocabulary": []
        if model.vectorizer is None
        else model.vectorizer.get_feature_names_out().tolist(),
        "idf": [] if model.vectorizer is None else model.vectorizer.idf_.tolist(),
        "cases": cases,
        "scenario_count": len(cases),
        "passed_cases": sum(row["passed"] for row in cases),
        "passed": all(row["passed"] for row in cases),
        "ranking_metrics": {
            "status": "not_calculated",
            "reason": "no_independent_relevance_judgments",
        },
        "limitations": [
            "fixed_product_facts_and_constraints_not_user_preference_quality",
            "known_catalog_fit_not_group_heldout_generalization_or_final_evaluation",
            "one_product_or_constant_features_do_not_establish_ranking_improvement",
            "business_category_price_and_browse_eligibility_are_explicit_demo_inputs",
            "no_performance_or_real_sale_stock_claim",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "manifest",
        "input",
        "source-receipt",
        "curation",
        "business-snapshot",
        "mapping",
        "spec",
        "output-dir",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        if ".pubburi" not in args.output_dir.resolve().parts:
            raise AuditError("reviewed_fit_requires_private_output_directory")
        if args.output_dir.exists():
            raise AuditError("existing_fit_output_must_be_preserved")
        catalog, _ = load_source_catalog(
            args.manifest, args.input, args.source_receipt, args.curation
        )
        snapshot, snapshot_hash = read_json(args.business_snapshot)
        mapping_data, mapping_hash = read_json(args.mapping)
        spec_data, spec_hash = read_json(args.spec)
        mapping = ReviewedMapping.model_validate(mapping_data)
        spec = ReviewedFitSpec.model_validate(spec_data)
        report, exports = build_exports(
            catalog, snapshot, snapshot_hash, mapping, datetime.now(UTC)
        )
        result = run_reviewed_fit(spec, catalog, exports, mapping, report, datetime.now(UTC))
        result.update(
            spec_sha256=spec_hash,
            mapping_sha256=mapping_hash,
            business_snapshot_sha256=snapshot_hash,
        )
        args.output_dir.mkdir(parents=True, exist_ok=False)
        write_receipt(args.output_dir, {"completed": False})
        (args.output_dir / "fit-report.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        write_receipt(
            args.output_dir,
            {
                "completed": True,
                "spec_sha256": spec_hash,
                "passed": result["passed"],
                "model_fingerprint": result["model_fingerprint"],
            },
        )
        print(
            json.dumps({key: result[key] for key in ("scenario_count", "passed_cases", "passed")})
        )
        return 0 if result["passed"] else 1
    except (OSError, ValueError, TypeError, KeyError) as error:
        code = str(error) if isinstance(error, AuditError) else type(error).__name__
        print("Reviewed catalog fit failed: " + code, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
