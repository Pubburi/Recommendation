"""Exercise the installed export gate with an explicitly authored business snapshot."""

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def smoke_business_export(
    python: Path,
    work: Path,
    manifest: Path,
    raw: Path,
    receipt: Path,
    curation: Path,
    catalog: dict,
) -> None:
    def digest(value):
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()

    def write(name, value):
        path = work / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    now = datetime.now(UTC).isoformat()
    snapshot = {
        "schema_version": 1,
        "snapshot_origin": "demo_fixture",
        "capture_method": "authored",
        "capture_started_at_utc": now,
        "capture_finished_at_utc": now,
        "records": [
            {
                "product": {
                    "data": {
                        "id": 37,
                        "name": "Authored fictional can",
                        "type": "맥주",
                        "price": 1000,
                        "img": "demo-fixture.webp",
                        "abv": 5.0,
                        "orderCount": 0,
                    },
                    "message": "ok",
                    "error": None,
                },
                "features": {
                    "data": {
                        "productId": 37,
                        "volumeMl": 500,
                        "description": None,
                        "tasteTags": None,
                        "aromaTags": None,
                        "sourceName": "Authored fixture",
                        "sourceUrl": None,
                        "sourceNote": "Not an actual product or license.",
                    },
                    "message": "ok",
                    "error": None,
                },
            }
        ],
    }
    snapshot_path = write("authored-business-snapshot.json", snapshot)
    row = catalog["records"][0]
    business = snapshot["records"][0]
    mapping = write(
        "authored-business-mapping.json",
        {
            "schema_version": 1,
            "algorithm": "reviewed-business-demo-export-v1",
            "source_catalog_sha256": digest(catalog),
            "business_snapshot_sha256": hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
            "reviewed_at_utc": datetime.now(UTC).isoformat(),
            "records": [
                {
                    "catalog_record_id": row["catalog_record_id"],
                    "backend_product_id": 37,
                    "product_response_sha256": digest(business["product"]),
                    "features_response_sha256": digest(business["features"]),
                    "source_variant_group": row["source_variant_group"],
                    "eligibility_scope": "public_browse_row_exists",
                    "demo_browse_eligible": True,
                    "price_kind": "demo_snapshot_krw",
                    "identity_review_note": "Explicit authored fixture mapping.",
                }
            ],
        },
    )
    output = work / ".pubburi" / "business-export"
    command = [str(python), "-I", "-m", "pubburi_recommendation.business_export"]
    for name, path in {
        "manifest": manifest,
        "input": raw,
        "source-receipt": receipt,
        "curation": curation,
        "business-snapshot": snapshot_path,
        "mapping": mapping,
        "output-dir": output,
    }.items():
        command += ["--" + name, str(path)]
    subprocess.run(command, cwd=work, check=True, timeout=10, stdout=subprocess.DEVNULL)
    report = json.loads((output / "export-report.json").read_text())
    b1 = json.loads((output / "b1-demo-request.json").read_text())
    b0 = json.loads((output / "b0-demo-request.json").read_text())
    if (
        report["exported_products"] != 1
        or not report["fixture_contract_validation"]
        or b1["catalog"][0]["product_id"] != 37
        or b0["catalog"][0]["product_id"] != 37
        or b1["catalog"][0]["taste_tags"] is not None
        or json.loads((output / "receipt.json").read_text())["completed"] is not True
    ):
        raise RuntimeError("Installed wheel violated reviewed business-demo export boundaries")
    # Declare facts and expected hard-constraint outcomes before the first fit CLI invocation.
    spec = write(
        "authored-reviewed-fit-spec.json",
        {
            "schema_version": 1,
            "experiment_id": "authored-reviewed-fit-v1",
            "evidence_kind": "authored_regression_fixture",
            "source_catalog_sha256": digest(catalog),
            "frozen_at_utc": datetime.now(UTC).isoformat(),
            "expected_facts": {
                row["catalog_record_id"]: {
                    "available": True,
                    "category": "맥주",
                    "price_krw": 1000,
                    "abv_percent": 5,
                    "volume_ml": 500,
                    "sku_group": row["source_variant_group"],
                    "taste_tags": None,
                    "aroma_tags": None,
                }
            },
            "scenarios": [
                {
                    "case_id": name,
                    "profile": profile,
                    "constraints": constraints,
                    "exclude_keys": [],
                    "expected_eligible_keys": keys,
                    "expected_item_count": count,
                    "expected_b1_fallback": fallback,
                    "fact_basis": "Declared authored numeric/category facts.",
                }
                for name, profile, constraints, keys, count, fallback in [
                    ("cold", {}, {}, [row["catalog_record_id"]], 1, "no_supported_preferences"),
                    ("category", {"categories": ["맥주"]}, {}, [row["catalog_record_id"]], 1, None),
                    ("hard", {}, {"max_abv_percent": 4.99}, [], 0, "no_eligible_products"),
                ]
            ],
        },
    )
    fit_output = work / ".pubburi" / "reviewed-fit"
    fit_command = [str(python), "-I", "-m", "pubburi_recommendation.reviewed_catalog_fit"]
    for name, path in {
        "manifest": manifest,
        "input": raw,
        "source-receipt": receipt,
        "curation": curation,
        "business-snapshot": snapshot_path,
        "mapping": mapping,
        "spec": spec,
        "output-dir": fit_output,
    }.items():
        fit_command += ["--" + name, str(path)]
    subprocess.run(fit_command, cwd=work, check=True, timeout=60, stdout=subprocess.DEVNULL)
    result = json.loads((fit_output / "fit-report.json").read_text())
    if (
        result["passed_cases"] != 3
        or not result["passed"]
        or result["fit_summary"]["training_products"] != 1
        or result["vocabulary"] != ["category:맥주"]
        or any(value["active"] for value in result["fit_summary"]["numeric_fit"].values())
        or result["ranking_metrics"]["status"] != "not_calculated"
    ):
        raise RuntimeError("Installed wheel violated frozen reviewed-fit facts or singleton limits")
