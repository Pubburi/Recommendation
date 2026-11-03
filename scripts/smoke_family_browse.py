"""Installed family-browse authority/export/fit using separate authored regression facts."""

import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime


def smoke_family_browse(python, work, manifest, raw, receipt, review, facts):
    scope = "reviewed_source_family_browse_demo_only"

    def write(name, value):
        path = work / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def digest(value):
        return hashlib.sha256(
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def run(module, arguments, *, rejected=False):
        command = [str(python), "-I", "-m", "pubburi_recommendation." + module]
        for name, value in arguments.items():
            command += ["--" + name, str(value)]
        result = subprocess.run(command, cwd=work, capture_output=True, text=True, timeout=60)
        if (not rejected and result.returncode != 0) or (rejected and result.returncode != 2):
            raise RuntimeError("Installed family-browse CLI violated expected success/rejection")
        return result

    curation = write(
        "authored-family-browse-curation.json",
        {
            "schema_version": 1,
            "algorithm": "reviewed-source-family-browse-demo-v1",
            "evidence_kind": "authored_regression_fixture",
            "input_sha256": sha(raw),
            "receipt_sha256": sha(receipt),
            "review_sha256": sha(review),
            "manifest_sha256": sha(manifest),
            "catalog_version": "authored-family-browse-v1",
            "reviewed_at_utc": datetime.now(UTC).isoformat(),
            "records": {
                qid: {
                    "catalog_record_id": "family-" + qid.lower(),
                    "source_variant_group": "group-" + qid.lower(),
                    "identity_scope": scope,
                    "checked_facts": {
                        "source_revision": 7,
                        "label": "Authored family, not actual source data",
                        "label_language": "mul",
                        **row,
                    },
                    "review_note": "Authored family browse only, no physical SKU/GTIN assignment.",
                }
                for qid, row in facts.items()
            },
        },
    )
    source_output = work / ".pubburi" / "family-browse-catalog"
    source_args = {
        "manifest": manifest,
        "input": raw,
        "receipt": receipt,
        "review": review,
        "curation": curation,
        "output-dir": source_output,
    }
    run("family_browse_catalog", source_args)
    catalog = json.loads((source_output / "source-catalog.json").read_text())
    if catalog["data_kind"] != scope or len(catalog["records"]) != 3:
        raise RuntimeError("Installed family-browse authority changed grain/count")
    records, mapping_rows, expected = [], [], {}
    now = datetime.now(UTC).isoformat()
    for pid, qid in enumerate(sorted(facts), start=501):
        key, group, abv = "family-" + qid.lower(), "group-" + qid.lower(), facts[qid]["abv_percent"]
        product = {
            "data": {
                "id": pid,
                "name": "Authored family, not actual source data",
                "type": "맥주",
                "price": 1000,
                "img": None,
                "abv": abv,
                "orderCount": 0,
            },
            "message": "ok",
            "error": None,
        }
        features = {
            "data": {
                "productId": pid,
                "volumeMl": None,
                "description": None,
                "tasteTags": None,
                "aromaTags": None,
                "sourceName": "Authored fixture",
                "sourceUrl": None,
                "sourceNote": "Not real SKU facts.",
            },
            "message": "ok",
            "error": None,
        }
        records.append({"product": product, "features": features})
        mapping_rows.append(
            {
                "catalog_record_id": key,
                "backend_product_id": pid,
                "product_response_sha256": digest(product),
                "features_response_sha256": digest(features),
                "source_variant_group": group,
                "eligibility_scope": scope,
                "demo_browse_eligible": True,
                "price_kind": "demo_snapshot_krw",
                "identity_review_note": "Explicit authored family mapping.",
            }
        )
        expected[key] = {
            "available": True,
            "category": "맥주",
            "price_krw": 1000,
            "abv_percent": abv,
            "volume_ml": None,
            "sku_group": group,
            "taste_tags": None,
            "aroma_tags": None,
        }
    snapshot = write(
        "authored-family-browse-business.json",
        {
            "schema_version": 1,
            "snapshot_origin": "demo_fixture",
            "capture_method": "authored",
            "capture_started_at_utc": now,
            "capture_finished_at_utc": now,
            "records": records,
        },
    )
    mapping_data = {
        "schema_version": 1,
        "algorithm": "reviewed-business-demo-export-v1",
        "source_catalog_sha256": digest(catalog),
        "business_snapshot_sha256": sha(snapshot),
        "reviewed_at_utc": datetime.now(UTC).isoformat(),
        "records": mapping_rows,
    }
    mapping = write("authored-family-browse-mapping.json", mapping_data)
    common = {
        "manifest": manifest,
        "input": raw,
        "source-receipt": receipt,
        "curation": curation,
        "family-review": review,
        "business-snapshot": snapshot,
        "mapping": mapping,
    }
    exported = work / ".pubburi" / "family-browse-export"
    run("business_export", {**common, "output-dir": exported})
    b1 = json.loads((exported / "b1-demo-request.json").read_text())
    if any(row["volume_ml"] is not None or row["taste_tags"] is not None for row in b1["catalog"]):
        raise RuntimeError("Installed family browse filled unknown volume/taste")
    keys = sorted(expected)
    spec = write(
        "authored-family-browse-fit-spec.json",
        {
            "schema_version": 1,
            "experiment_id": "authored-family-browse-fit",
            "evidence_kind": "authored_regression_fixture",
            "source_catalog_sha256": digest(catalog),
            "frozen_at_utc": datetime.now(UTC).isoformat(),
            "expected_facts": expected,
            "scenarios": [
                {
                    "case_id": name,
                    "profile": profile,
                    "constraints": constraints,
                    "expected_eligible_keys": eligible,
                    "expected_item_count": len(eligible),
                    "expected_b1_fallback": fallback,
                    "fact_basis": "Fixed authored source quantities and unknown volume.",
                }
                for name, profile, constraints, eligible, fallback in (
                    ("cold", {}, {}, keys, "no_supported_preferences"),
                    ("abv", {"preferred_abv_percent": 5}, {}, keys, None),
                    ("volume", {"preferred_volume_ml": 330}, {}, keys, "no_supported_preferences"),
                    (
                        "hard",
                        {},
                        {"max_abv_percent": 10},
                        ["family-q1"],
                        "no_supported_preferences",
                    ),
                )
            ],
        },
    )
    fitted = work / ".pubburi" / "family-browse-fit"
    run("reviewed_catalog_fit", {**common, "spec": spec, "output-dir": fitted})
    result = json.loads((fitted / "fit-report.json").read_text())
    if (
        not result["passed"]
        or result["passed_cases"] != 4
        or result["fit_scope"] != "known_mapped_family_browse_demo"
        or result["fit_summary"]["training_products"] != 3
        or not result["fit_summary"]["numeric_fit"]["abv_percent"]["active"]
        or result["fit_summary"]["numeric_fit"]["volume_ml"]["active"]
        or result["ranking_metrics"]["status"] != "not_calculated"
    ):
        raise RuntimeError("Installed family browse changed existing fit/independent fact checks")
    # Preserve a separate unchanged input copy for the later checked-artifact HTTP
    # consumer. The wrong-origin test below keeps its original scope and failure.
    provider_snapshot = work / "authored-provider-business.json"
    provider_mapping = work / "authored-provider-mapping.json"
    shutil.copy2(snapshot, provider_snapshot)
    shutil.copy2(mapping, provider_mapping)
    provider_common = {
        **common,
        "business-snapshot": provider_snapshot,
        "mapping": provider_mapping,
    }
    provider_cases = []
    for route in ("content", "exploration", "similar", "context", "feedback"):
        reference = route in ("similar", "context", "feedback")
        selected = keys[1:] if route == "similar" else keys[1:2] if reference else keys
        provider_cases.append(
            {
                "case_id": route,
                "provider": route,
                "profile": {}
                if reference
                else {"categories": ["맥주"], "preferred_abv_percent": 5},
                "reference_keys": [keys[0]]
                if route == "similar"
                else [keys[0], keys[2]]
                if route == "context"
                else [],
                "positive_keys": [keys[0]] if route == "feedback" else [],
                "negative_keys": [keys[2]] if route == "feedback" else [],
                "expected_eligible_keys": selected,
                "expected_item_keys": selected,
                "expected_comparisons": {key: keys[0] if reference else None for key in selected},
                "expected_fallback": None,
                "expected_representation_fitted": True,
                "fact_basis": (
                    "Authored ABV5/15/25 and exact groups; midpoint context tie keeps smaller ID."
                ),
            }
        )
    provider_spec = write(
        "authored-provider-spec.json",
        {
            "schema_version": 1,
            "experiment_id": "authored-checked-provider-http",
            "evidence_kind": "authored_regression_fixture",
            "source_catalog_sha256": digest(catalog),
            "frozen_at_utc": datetime.now(UTC).isoformat(),
            "expected_model_fingerprint": result["model_fingerprint"],
            "expected_facts": expected,
            "cases": provider_cases,
        },
    )
    write(
        "provider-acceptance-context.json",
        {
            "arguments": {key: str(value) for key, value in provider_common.items()},
            "export-dir": str(exported),
            "spec": str(provider_spec),
        },
    )
    # Same hashes/authorities cannot convert this scope into an ordinary service snapshot.
    snap = json.loads(snapshot.read_text())
    snap.update(snapshot_origin="existing_local_catalog", capture_method="http_read")
    write(snapshot.name, snap)
    mapping_data.update(
        business_snapshot_sha256=sha(snapshot), reviewed_at_utc=datetime.now(UTC).isoformat()
    )
    write(mapping.name, mapping_data)
    rejected_output = work / ".pubburi" / "family-browse-wrong-origin"
    rejection = run("business_export", {**common, "output-dir": rejected_output}, rejected=True)
    if (
        "family_browse_requires_owned_offline_demo_origin" not in rejection.stderr
        or rejected_output.exists()
    ):
        raise RuntimeError("Installed family browse accepted an ordinary service origin")
