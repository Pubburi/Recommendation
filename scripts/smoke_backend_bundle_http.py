"""Installed fresh bundle CLI feeding the unchanged B0/B1 HTTP on authored facts."""

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def smoke_backend_bundle_http(python, work, base_url, request_json):
    context = json.loads((work / "provider-acceptance-context.json").read_text())
    args = {**context["arguments"], "export-dir": context["export-dir"]}
    output = work / ".pubburi" / "backend-catalog-bundle"

    def run(target):
        command = [str(python), "-I", "-m", "pubburi_recommendation.backend_catalog_bundle"]
        for key, value in {**args, "output-dir": target}.items():
            command += ["--" + key, str(value)]
        return subprocess.run(command, cwd=work, capture_output=True, text=True, timeout=30)

    result = run(output)
    if result.returncode != 0:
        raise RuntimeError("Installed checked Backend bundle CLI failed")
    raw = (output / "catalog-bundle.json").read_bytes()
    bundle = json.loads(raw)
    receipt = json.loads((output / "receipt.json").read_text())
    if (
        receipt["completed"] is not True
        or receipt["records"] != 3
        or receipt["bundle_sha256"] != hashlib.sha256(raw).hexdigest()
        or set(bundle)
        != {
            "schema_version",
            "algorithm",
            "catalog",
            "records",
            "checked_export",
            "service_catalog_approved",
            "model_loaded",
            "current_business_revalidation_required",
            "valid_until_utc",
        }
        or bundle["checked_export"]["mode"] != "fresh_demo_snapshot"
        or bundle["service_catalog_approved"] is not False
        or bundle["model_loaded"] is not False
        or bundle["current_business_revalidation_required"] is not True
        or datetime.fromisoformat(bundle["valid_until_utc"]) <= datetime.now(UTC)
    ):
        raise RuntimeError("Installed bundle changed completion, pin, freshness or DEMO scope")
    validation = subprocess.run(
        [
            str(python),
            "-I",
            "-c",
            """
import copy, json, sys
from pydantic import ValidationError
from pubburi_recommendation.backend_catalog_bundle import BackendCatalogBundle
value = json.loads(sys.stdin.read())
BackendCatalogBundle.model_validate(value)
for fault in ("origin", "family_volume", "family_empty_tags"):
    changed = copy.deepcopy(value)
    if fault == "origin":
        changed["checked_export"]["snapshot_origin"] = "existing_local_catalog"
    elif fault == "family_volume":
        changed["catalog"][0]["volume_ml"] = 500
        changed["records"][0]["features"]["data"]["volumeMl"] = 500
    else:
        changed["records"][0]["features"]["data"]["tasteTags"] = []
    try:
        BackendCatalogBundle.model_validate(changed)
    except ValidationError:
        continue
    raise SystemExit("Installed bundle accepted incompatible " + fault)
assert not {"numpy", "sklearn", "pubburi_recommendation.content_model"} & set(sys.modules)
""",
        ],
        input=json.dumps(bundle),
        cwd=work,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if validation.returncode != 0:
        raise RuntimeError("Installed typed bundle failed scope/unknown validation")
    snapshot = json.loads(Path(args["business-snapshot"]).read_text())
    by_id = {r["product"]["data"]["id"]: r for r in snapshot["records"]}
    for row, product in zip(bundle["records"], bundle["catalog"], strict=True):
        if (
            row["product"] != by_id[product["product_id"]]["product"]
            or row["features"] != by_id[product["product_id"]]["features"]
            or row["sku_group"] != product["sku_group"]
            or row["backend_product_id"] != product["product_id"]
            or product["volume_ml"] is not None
            or product["taste_tags"] is not None
        ):
            raise RuntimeError("Installed bundle changed original business facts/unknown/group")
    # Independent authored ABV5/15/25: only the first two satisfy max15. The first
    # is the exact explicit target; do not treat their ordering as user quality.
    body = {"catalog": bundle["catalog"], "constraints": {"max_abv_percent": 15}}
    content = request_json(
        base_url,
        "/v1/recommendations/content",
        body={
            **body,
            "profile": {"categories": ["맥주"], "preferred_abv_percent": 5},
            "include_explanations": True,
        },
    )
    baseline = request_json(
        base_url,
        "/v1/recommendations/baseline",
        body={
            **body,
            "catalog": [
                {
                    k: v
                    for k, v in p.items()
                    if k in {"product_id", "available", "category", "price_krw", "abv_percent"}
                }
                for p in bundle["catalog"]
            ],
        },
    )
    if (
        [p["product_id"] for p in content["items"]] != [501, 502]
        or [p["product_id"] for p in baseline["items"]] != [501, 502]
        or content["eligible_count"] != 2
        or content["fallback_reason"] is not None
        or content["items"][0]["score"] != 1
    ):
        raise RuntimeError("Installed bundle did not preserve declared B0/B1 factual conditions")
    original = Path(context["export-dir"]) / "b1-demo-request.json"
    saved = original.read_bytes()
    original.write_bytes(saved + b" ")
    rejected = work / ".pubburi" / "backend-bundle-rejected"
    try:
        if run(rejected).returncode != 2 or rejected.exists():
            raise RuntimeError("Installed bundle approved a modified completed export")
    finally:
        original.write_bytes(saved)
