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
