"""Consume a checked DEMO export through existing B1 HTTP and inspect frozen facts."""

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from pydantic import Field, ValidationError, model_validator

from pubburi_recommendation.baseline import Constraints, ContractModel
from pubburi_recommendation.catalog_audit import (
    MAX_INPUT_BYTES,
    AuditError,
    parse_json_bytes,
    read_json,
)
from pubburi_recommendation.checked_export import load_checked_export
from pubburi_recommendation.content_api import ContentRecommendationResponse
from pubburi_recommendation.content_contracts import ContentProfile
from pubburi_recommendation.context_api import ContextRecommendationResponse
from pubburi_recommendation.exploration import ExplorationResponse
from pubburi_recommendation.feedback_api import FeedbackRecommendationResponse
from pubburi_recommendation.package_identity_audit import Hash
from pubburi_recommendation.reviewed_catalog_fit import FrozenFacts
from pubburi_recommendation.scenario_evaluation import eligibility_issues, expected_reasons
from pubburi_recommendation.similar_api import SimilarRecommendationResponse
from pubburi_recommendation.source_catalog import Key, Note
from pubburi_recommendation.wikidata_collect import write_receipt

Provider = Literal["content", "exploration", "similar", "context", "feedback"]
RESPONSES = {
    "content": ContentRecommendationResponse,
    "exploration": ExplorationResponse,
    "similar": SimilarRecommendationResponse,
    "context": ContextRecommendationResponse,
    "feedback": FeedbackRecommendationResponse,
}


class ProviderCase(ContractModel):
    case_id: Key
    provider: Provider
    profile: ContentProfile = Field(default_factory=ContentProfile)
    constraints: Constraints = Field(default_factory=Constraints)
    exclude_keys: list[Key] = Field(default_factory=list, max_length=1000)
    reference_keys: list[Key] = Field(default_factory=list, max_length=20)
    positive_keys: list[Key] = Field(default_factory=list, max_length=20)
    negative_keys: list[Key] = Field(default_factory=list, max_length=20)
    limit: int = Field(default=12, ge=1, le=100)
    expected_eligible_keys: list[Key] | None = Field(max_length=1000)
    expected_item_keys: list[Key] = Field(max_length=100)
    expected_comparisons: dict[Key, Key | None] = Field(max_length=100)
    expected_fallback: str | None = Field(max_length=80)
    expected_representation_fitted: bool
    fact_basis: Note


class ProviderSpec(ContractModel):
    schema_version: Literal[1]
    experiment_id: Key
    evidence_kind: Literal["reviewed_public_source", "authored_regression_fixture"]
    source_catalog_sha256: Hash
    frozen_at_utc: str = Field(min_length=20, max_length=40)
    expected_model_fingerprint: Hash
    expected_facts: dict[Key, FrozenFacts] = Field(min_length=1, max_length=1000)
    cases: list[ProviderCase] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def coherent_keys(self):
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("provider_case_ids_must_be_unique")
        known = set(self.expected_facts)
        for case in self.cases:
            groups = (
                case.exclude_keys,
                case.reference_keys,
                case.positive_keys,
                case.negative_keys,
                case.expected_item_keys,
                case.expected_eligible_keys or [],
            )
            if any(len(keys) != len(set(keys)) or not set(keys) <= known for keys in groups):
                raise ValueError("provider_case_keys_must_be_unique_and_known")
            if case.constraints.exclude_product_ids:
                raise ValueError("provider_cases_require_mapping_keys_not_unbound_ids")
            if set(case.expected_comparisons) != set(case.expected_item_keys) or any(
                key is not None and key not in known for key in case.expected_comparisons.values()
            ):
                raise ValueError("provider_comparisons_must_cover_returned_known_keys")
            if len(case.expected_item_keys) > case.limit or not set(case.expected_item_keys) <= set(
                case.expected_eligible_keys or []
            ):
                raise ValueError("provider_expected_items_conflict_with_eligibility_or_limit")
            if (
                (case.provider == "similar" and len(case.reference_keys) != 1)
                or (case.provider == "context" and not case.reference_keys)
                or (case.provider not in ("similar", "context") and case.reference_keys)
            ):
                raise ValueError("provider_reference_keys_conflict_with_route")
            if case.provider != "feedback" and (case.positive_keys or case.negative_keys):
                raise ValueError("feedback_keys_require_feedback_route")
            if case.provider in ("similar", "context") and case.profile != ContentProfile():
                raise ValueError("reference_routes_do_not_accept_user_profile")
            for winner in case.expected_comparisons.values():
                if (
                    (case.provider in ("content", "exploration") and winner is not None)
                    or (
                        case.provider in ("similar", "context")
                        and winner not in case.reference_keys
                    )
                    or (
                        case.provider == "feedback"
                        and winner is not None
                        and winner not in case.positive_keys
                    )
                ):
                    raise ValueError("declared_comparison_conflicts_with_input_source")
        return self


def mapped_request(case, checked):
    ids = {row.catalog_record_id: row.backend_product_id for row in checked.mapping.records}
    constraints = case.constraints.model_copy(
        update={"exclude_product_ids": [ids[key] for key in case.exclude_keys]}
    )
    body = {
        "catalog": checked.request.model_dump()["catalog"],
        "constraints": constraints.model_dump(),
        "limit": case.limit,
        "include_explanations": True,
    }
    if case.provider in ("content", "exploration", "feedback"):
        body["profile"] = case.profile.model_dump()
    if case.provider == "similar":
        body["reference_product_id"] = ids[case.reference_keys[0]]
    if case.provider == "context":
        body["reference_product_ids"] = [ids[key] for key in case.reference_keys]
    if case.provider == "feedback":
        body["feedback"] = {
            "positive_product_ids": [ids[key] for key in case.positive_keys],
            "not_interested_product_ids": [ids[key] for key in case.negative_keys],
        }
    if len(json.dumps(body, ensure_ascii=False).encode()) > 524288:
        raise AuditError("provider_request_exceeds_service_body_limit")
    return body, constraints


def eligible_products(case, checked, constraints):
    by_key = {
        row.catalog_record_id: next(
            product
            for product in checked.request.catalog
            if product.product_id == row.backend_product_id
        )
        for row in checked.mapping.records
    }
    products = checked.request.catalog
    if case.provider in ("similar", "context"):
        references = [by_key[key] for key in case.reference_keys]
        if not any(product.available for product in references):
            return None
        groups = {product.sku_group for product in references}
        products = [product for product in products if product.sku_group not in groups]
    elif case.provider == "feedback":
        groups = {by_key[key].sku_group for key in case.negative_keys + case.positive_keys}
        products = [product for product in products if product.sku_group not in groups]
    return {
        product.product_id for product in products if not eligibility_issues(product, constraints)
    }


def prepare_cases(spec, checked, now):
    from pubburi_recommendation.business_export import utc_time

    if utc_time(spec.frozen_at_utc) > now or (
        spec.source_catalog_sha256 != checked.metadata["source_catalog_sha256"]
        or spec.evidence_kind != checked.metadata["evidence_kind"]
    ):
        raise AuditError("provider_frozen_source_or_time_conflict")
    ids = {row.catalog_record_id: row.backend_product_id for row in checked.mapping.records}
    if set(ids) != set(spec.expected_facts):
        raise AuditError("provider_frozen_facts_must_cover_exact_mapping")
    by_id = {product.product_id: product for product in checked.request.catalog}
    for key, facts in spec.expected_facts.items():
        if any(
            getattr(by_id[ids[key]], name) != value for name, value in facts.model_dump().items()
        ):
            raise AuditError("provider_frozen_product_fact_conflict")
    prepared = []
    for case in spec.cases:
        body, constraints = mapped_request(case, checked)
        eligible = eligible_products(case, checked, constraints)
        expected = (
            None
            if case.expected_eligible_keys is None
            else {ids[key] for key in case.expected_eligible_keys}
        )
        if eligible != expected:
            raise AuditError("provider_frozen_eligibility_conflicts_before_http")
        prepared.append((case, body, constraints))
    return prepared


def evidence_issues(item, product, profile, constraints, fallback, comparison):
    """Inspect facts and original contributions; never import the scorer/formatter."""
    issues = []
    positive = sorted(item.contributions, key=lambda p: (-p.contribution, p.component, p.feature))
    if (
        any(part.contribution <= 0 for part in positive)
        or not math.isclose(item.score, sum(part.contribution for part in positive), abs_tol=1e-9)
        or bool(positive) != bool(item.score > 0)
    ):
        issues.append("contribution_score_conflict")
    evidence = []
    for part in positive:
        if part.component == "text":
            namespace, separator, atom = part.feature.partition(":")
            allowed = {
                "category": ([product.category], profile.categories, "category_match"),
                "taste": (product.taste_tags or [], profile.taste_tags, "taste_match"),
                "aroma": (product.aroma_tags or [], profile.aroma_tags, "aroma_match"),
            }.get(namespace)
            if not separator or allowed is None or atom not in allowed[0] or atom not in allowed[1]:
                issues.append("unsupported_text_contribution")
                continue
            evidence.append((allowed[2], atom, atom, part.contribution, None))
        else:
            actual = getattr(product, part.component)
            target = getattr(profile, "preferred_" + part.component)
            if actual is None or target is None or part.feature != part.component:
                issues.append("unsupported_numeric_contribution")
            evidence.append(
                (
                    "abv_comparison" if part.component == "abv_percent" else "volume_comparison",
                    actual,
                    target,
                    part.contribution,
                    "vol%" if part.component == "abv_percent" else "mL",
                )
            )
    hard = expected_reasons(constraints, baseline=False)
    hard_codes = {"available", "category_match", "price_within_range", "abv_within_range"}
    if set(item.reasons) & hard_codes != hard or ("content_similarity" in item.reasons) != (
        item.score > 0
    ):
        issues.append("item_reason_conflict")
    explanation = item.explanation
    if explanation is None:
        return issues + ["missing_explanation"]
    if explanation.comparison.model_dump() != comparison:
        issues.append("explanation_comparison_conflict")
    basis = (
        "content_similarity"
        if item.score > 0
        else (
            "deterministic_baseline"
            if "deterministic_baseline" in item.reasons
            else "no_shared_features"
        )
    )
    if explanation.basis != basis or explanation.fallback_reason != fallback:
        issues.append("explanation_basis_or_fallback_conflict")
    if (
        explanation.total_positive_contributions != len(positive)
        or (explanation.score_evidence_truncated != (len(positive) > 3))
        or len(explanation.score_evidence) != min(3, len(positive))
    ):
        issues.append("explanation_contribution_count_conflict")
    for shown, expected in zip(explanation.score_evidence, evidence[:3], strict=False):
        if (
            shown.kind,
            shown.actual_value,
            shown.target_value,
            shown.contribution,
            getattr(shown, "unit", None),
        ) != expected:
            issues.append("explanation_fact_or_contribution_conflict")
    expected_filters = {"availability_filter": {"actual_value": True}}
    if constraints.categories:
        expected_filters["category_filter"] = {
            "actual_value": product.category,
            "allowed_category_count": len(set(constraints.categories)),
        }
    for field, lower, upper, kind in (
        ("price_krw", constraints.min_price_krw, constraints.max_price_krw, "price_filter"),
        ("abv_percent", constraints.min_abv_percent, constraints.max_abv_percent, "abv_filter"),
    ):
        if lower is not None or upper is not None:
            expected_filters[kind] = {
                "actual_value": getattr(product, field),
                "minimum": lower,
                "maximum": upper,
            }
    if {row.kind for row in explanation.filter_evidence} != set(expected_filters) or len(
        explanation.filter_evidence
    ) != len(expected_filters):
        issues.append("explanation_filter_set_conflict")
    for row in explanation.filter_evidence:
        if any(
            getattr(row, name) != value
            for name, value in expected_filters.get(row.kind, {}).items()
        ):
            issues.append("explanation_filter_fact_conflict")
    if len(explanation.model_dump_json().encode()) > 4096:
        issues.append("explanation_size_conflict")
    return issues


def feedback_metadata_issues(case, parsed, by_id, ids, active_numeric):
    """Check references/evaluation from frozen input facts, even with no returned items."""
    negative_ids = {ids[key] for key in case.negative_keys}
    positive_ids = {ids[key] for key in case.positive_keys}
    negative_groups = {by_id[pid].sku_group for pid in negative_ids}
    positive_groups = {by_id[pid].sku_group for pid in positive_ids}
    expected_negatives = [
        (pid, by_id[pid].sku_group, "available" if by_id[pid].available else "unavailable")
        for pid in sorted(negative_ids)
    ]
    expected_positives = []
    diagnostics = {}
    informative_count = evaluated_count = 0
    for pid in sorted(positive_ids):
        product = by_id[pid]
        state = (
            "blocked"
            if pid in negative_ids or product.sku_group in negative_groups
            else ("available" if product.available else "unavailable")
        )
        expected_positives.append((pid, product.sku_group, state))
        if state != "available":
            diagnostics[pid] = (None, None, None)
            continue
        # Fit includes every catalog reference, so its own atomic text is in the
        # vocabulary. No scorer, weighting or observed response decides these counts.
        supported = (
            int(product.category is not None)
            + len(product.taste_tags or [])
            + len(product.aroma_tags or [])
        )
        numeric = [
            field
            for field in ("abv_percent", "volume_ml")
            if field in active_numeric and getattr(product, field) is not None
        ]
        diagnostics[pid] = (supported, 0, numeric)
        evaluated_count += 1
        informative_count += bool(supported or numeric)
    issues = []
    if [
        (r.product_id, r.sku_group, r.state) for r in parsed.not_interested_references
    ] != expected_negatives:
        issues.append("feedback_negative_reference_facts_conflict")
    if [
        (r.product_id, r.sku_group, r.state) for r in parsed.positive_references
    ] != expected_positives:
        issues.append("feedback_positive_reference_facts_conflict")
    for reference in parsed.positive_references:
        expected = diagnostics.get(reference.product_id)
        if expected is None:
            continue  # Its unbound ID/list is already a reference-facts violation.
        if (
            reference.supported_profile_tokens,
            reference.unknown_profile_tokens,
            reference.active_numeric_preferences,
        ) != expected:
            issues.append("feedback_reference_evaluation_conflict")
        if expected[0] is None:
            if reference.fallback_reason is not None:
                issues.append("feedback_unevaluated_reference_fallback_conflict")
        else:
            if not case.expected_eligible_keys:
                allowed_fallbacks = {"no_eligible_products"}
            elif not (expected[0] or expected[2]):
                allowed_fallbacks = {"no_supported_preferences"}
            elif any(
                ids[winner] == reference.product_id
                for winner in case.expected_comparisons.values()
                if winner is not None
            ):
                allowed_fallbacks = {None}
            else:
                allowed_fallbacks = {None, "no_matching_features"}
            if reference.fallback_reason not in allowed_fallbacks:
                issues.append("feedback_evaluated_reference_fallback_conflict")
    nonnegative = [
        p
        for p in by_id.values()
        if p.product_id not in negative_ids and p.sku_group not in negative_groups
    ]
    remaining = [p for p in nonnegative if p.sku_group not in positive_groups]
    if (
        parsed.evaluated_positive_count != evaluated_count
        or parsed.informative_positive_count != informative_count
        or parsed.ranking_mode != ("positive_feedback" if informative_count else "profile_fallback")
    ):
        issues.append("feedback_counts_or_mode_conflict")
    if parsed.excluded_not_interested_count != len(by_id) - len(
        nonnegative
    ) or parsed.excluded_positive_group_count != len(nonnegative) - len(remaining):
        issues.append("feedback_group_exclusion_counts_conflict")
    return issues


def inspect_response(case, body, constraints, response, checked, spec):
    try:
        parsed = RESPONSES[case.provider].model_validate(response)
    except ValidationError:
        return ["provider_response_schema_conflict"]
    ids = {row.catalog_record_id: row.backend_product_id for row in checked.mapping.records}
    by_id = {product.product_id: product for product in checked.request.catalog}
    issues = []
    if [item.product_id for item in parsed.items] != [ids[key] for key in case.expected_item_keys]:
        issues.append("declared_items_or_order_conflict")
    count = None if case.expected_eligible_keys is None else len(case.expected_eligible_keys)
    if parsed.eligible_count != count or parsed.fallback_reason != case.expected_fallback:
        issues.append("declared_eligibility_or_fallback_conflict")
    fingerprint = spec.expected_model_fingerprint if case.expected_representation_fitted else None
    if (
        parsed.representation_fitted != case.expected_representation_fitted
        or parsed.model_fingerprint != fingerprint
    ):
        issues.append("declared_fit_or_fingerprint_conflict")
    key_by_id = {value: key for key, value in ids.items()}
    if case.provider == "similar":
        reference = by_id[ids[case.reference_keys[0]]]
        if (parsed.reference_product_id, parsed.reference_sku_group, parsed.reference_state) != (
            reference.product_id,
            reference.sku_group,
            "available" if reference.available else "unavailable",
        ):
            issues.append("similar_reference_facts_conflict")
    if case.provider == "context":
        expected_references = sorted(
            (by_id[ids[key]] for key in case.reference_keys), key=lambda p: p.product_id
        )
        if [(r.product_id, r.sku_group, r.state) for r in parsed.references] != [
            (p.product_id, p.sku_group, "available" if p.available else "unavailable")
            for p in expected_references
        ] or parsed.evaluated_reference_count != sum(p.available for p in expected_references):
            issues.append("context_reference_facts_conflict")
    active_numeric = {
        field
        for field in ("abv_percent", "volume_ml")
        if len(
            {
                getattr(product, field)
                for product in checked.request.catalog
                if getattr(product, field) is not None
            }
        )
        > 1
    }
    if case.provider == "feedback":
        issues.extend(feedback_metadata_issues(case, parsed, by_id, ids, active_numeric))
    for item in parsed.items:
        key = key_by_id.get(item.product_id)
        if key not in case.expected_comparisons:
            issues.append("unbound_item_comparison")
            continue
        winner = case.expected_comparisons[key]
        profile = case.profile
        comparison = {"kind": "profile"}
        if winner is not None:
            product = by_id[ids[winner]]
            profile = ContentProfile(
                categories=[] if product.category is None else [product.category],
                taste_tags=product.taste_tags or [],
                aroma_tags=product.aroma_tags or [],
                preferred_abv_percent=product.abv_percent,
                preferred_volume_ml=product.volume_ml,
            )
            comparison = {"kind": "reference_product", "product_id": product.product_id}
        if (
            case.provider == "similar"
            and parsed.reference_product_id != ids[case.reference_keys[0]]
        ):
            issues.append("similar_reference_conflict")
        if case.provider == "context":
            if [(m.product_id, m.reference_product_id) for m in parsed.matches] != [
                (ids[k], ids[case.expected_comparisons[k]]) for k in case.expected_item_keys
            ]:
                issues.append("context_winning_reference_conflict")
        if case.provider == "feedback":
            match = next((m for m in parsed.matches if m.product_id == item.product_id), None)
            expected_source = (
                "positive_feedback"
                if winner is not None
                else "profile"
                if item.score > 0
                else "baseline"
            )
            if (
                match is None
                or match.source != expected_source
                or match.positive_product_id != (ids[winner] if winner else None)
            ):
                issues.append("feedback_winning_source_conflict")
        issues.extend(
            evidence_issues(
                item,
                by_id[item.product_id],
                profile,
                constraints,
                parsed.fallback_reason,
                comparison,
            )
        )
        if any(
            part.component != "text" and part.component not in active_numeric
            for part in item.contributions
        ):
            issues.append("unsupported_numeric_scale")
    if case.provider in ("context", "feedback") and len(parsed.matches) != len(parsed.items):
        issues.append("matches_count_conflict")
    return sorted(set(issues))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def loopback_base_url(value):
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or not parsed.port
        or (
            parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in ("", "/")
        )
    ):
        raise AuditError("provider_acceptance_requires_explicit_owned_loopback_origin")
    return value.rstrip("/")


def post_json(base_url, provider, body):
    request = Request(
        base_url + "/v1/recommendations/" + provider,
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=30) as response:
            if response.status != 200 or response.headers.get_content_type() != "application/json":
                raise AuditError("provider_http_success_json_required")
            content = response.read(MAX_INPUT_BYTES + 1)
    except HTTPError as error:
        raise AuditError("provider_http_request_failed") from error
    return parse_json_bytes(content)[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "export-dir",
        "manifest",
        "input",
        "source-receipt",
        "curation",
        "business-snapshot",
        "mapping",
        "spec",
        "base-url",
        "output-dir",
    ):
        parser.add_argument("--" + name, type=str if name == "base-url" else Path, required=True)
    parser.add_argument("--family-review", type=Path)
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    try:
        if ".pubburi" not in args.output_dir.resolve().parts or args.output_dir.exists():
            raise AuditError("provider_acceptance_requires_new_private_output")
        base_url = loopback_base_url(args.base_url)

        def load():
            return load_checked_export(
                args.export_dir,
                args.manifest,
                args.input,
                args.source_receipt,
                args.curation,
                args.business_snapshot,
                args.mapping,
                family_review=args.family_review,
                replay=args.replay,
            )

        checked = load()
        data, spec_hash = read_json(args.spec)
        spec = ProviderSpec.model_validate(data)
        prepared = prepare_cases(spec, checked, datetime.now(UTC))
        args.output_dir.mkdir(parents=True, exist_ok=False)
        write_receipt(args.output_dir, {"completed": False})
        cases = []
        for case, body, constraints in prepared:
            response = post_json(base_url, case.provider, body)
            issues = inspect_response(case, body, constraints, response, checked, spec)
            cases.append(
                {
                    "case_id": case.case_id,
                    "provider": case.provider,
                    "request": body,
                    "response": response,
                    "issues": issues,
                    "passed": not issues,
                }
            )
        final = load()
        for key in (
            "artifact_sha256",
            "source_catalog_sha256",
            "business_snapshot_sha256",
            "mapping_sha256",
        ):
            if final.metadata[key] != checked.metadata[key]:
                raise AuditError("provider_inputs_changed_during_http_acceptance")
        _, final_spec_hash = read_json(args.spec)
        if final_spec_hash != spec_hash:
            raise AuditError("provider_spec_changed_during_http_acceptance")
        report = {
            "algorithm": "reviewed-provider-http-acceptance-v1",
            "experiment_id": spec.experiment_id,
            "executed_at_utc": datetime.now(UTC).isoformat(),
            "spec_sha256": spec_hash,
            "frozen_at_utc": spec.frozen_at_utc,
            "checked_export": checked.metadata,
            "cases": cases,
            "case_count": len(cases),
            "passed_contract_cases": sum(c["passed"] for c in cases),
            "passed": all(c["passed"] for c in cases),
            "limitations": [
                "mapped_demo_contracts_not_user_preference_quality",
                "request_local_fit_not_model_restore_or_service_catalog_adoption",
                "no_new_source_or_business_capture_or_performance_claim",
            ],
        }
        (args.output_dir / "acceptance-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        write_receipt(
            args.output_dir,
            {
                "completed": True,
                "passed": report["passed"],
                "spec_sha256": spec_hash,
                "mode": checked.metadata["mode"],
            },
        )
        print(
            json.dumps(
                {key: report[key] for key in ("case_count", "passed_contract_cases", "passed")}
            )
        )
        return 0 if report["passed"] else 1
    except (OSError, ValueError, TypeError, KeyError) as error:
        reason = str(error) if isinstance(error, AuditError) else type(error).__name__
        print("Reviewed provider acceptance failed: " + reason, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
