"""Run source-container curation from an isolated wheel using authored source shapes."""

import copy
import hashlib
import json
import subprocess
from pathlib import Path

from smoke_business_export import smoke_business_export


def smoke_source_catalog(python: Path, work: Path, manifest: Path, authored_entity: dict) -> None:
    def write(name, payload):
        path = work / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    entity = copy.deepcopy(authored_entity)
    entity["claims"]["P31"] = [
        {
            "rank": "normal",
            "mainsnak": {
                "snaktype": "value",
                "datavalue": {"type": "wikibase-entityid", "value": {"id": qid}},
            },
        }
        for qid in ("Q1121690", "Q15075508")
    ]
    entity["claims"]["P2665"][0]["mainsnak"]["datavalue"]["type"] = "quantity"
    entity["claims"]["P2234"] = [
        {
            "rank": "normal",
            "mainsnak": {
                "snaktype": "value",
                "datavalue": {
                    "type": "quantity",
                    "value": {"amount": "0.5", "unit": "http://www.wikidata.org/entity/Q11582"},
                },
            },
        }
    ]
    raw = write("authored-container.json", {"success": 1, "entities": {"Q1": entity}})
    collection = work / ".pubburi" / "container-collection"
    subprocess.run(
        [
            str(python),
            "-I",
            "-m",
            "pubburi_recommendation.wikidata_collect",
            "--manifest",
            str(manifest),
            "--ids",
            "Q1",
            "--snapshot",
            str(raw),
            "--output-dir",
            str(collection),
        ],
        cwd=work,
        check=True,
        timeout=10,
        stdout=subprocess.DEVNULL,
    )
    receipt = collection / "receipt.json"
    curation = write(
        "authored-container-curation.json",
        {
            "schema_version": 1,
            "algorithm": "source-container-curation-v1",
            "evidence_kind": "authored_regression_fixture",
            "input_sha256": sha(raw),
            "receipt_sha256": sha(receipt),
            "manifest_sha256": sha(manifest),
            "catalog_version": "authored-container-v1",
            "reviewed_at_utc": "2026-11-01T00:00:00Z",
            "records": {
                "Q1": {
                    "catalog_record_id": "authored-container-1",
                    "source_variant_group": "authored-family",
                    "identity_scope": "single_container_source_candidate",
                    "checked_facts": {
                        "gtin": "12345670",
                        "container_class_id": "Q1121690",
                        "volume_ml": 500,
                        "abv_percent": 5,
                    },
                    "corroboration_url": "https://example.org/authored-not-an-actual-listing",
                    "corroboration_publisher": "Authored fixture",
                    "review_note": "Fictional facts; no actual identity or rights approval.",
                    "mixed_type_interpretation": "Authored container scope; retain conflict.",
                }
            },
        },
    )
    output = work / ".pubburi" / "source-catalog"
    subprocess.run(
        [
            str(python),
            "-I",
            "-m",
            "pubburi_recommendation.source_catalog",
            "--manifest",
            str(manifest),
            "--input",
            str(raw),
            "--receipt",
            str(receipt),
            "--curation",
            str(curation),
            "--output-dir",
            str(output),
        ],
        cwd=work,
        check=True,
        timeout=10,
        stdout=subprocess.DEVNULL,
    )
    report = json.loads((output / "curation-report.json").read_text())
    catalog = json.loads((output / "source-catalog.json").read_text())
    row = catalog["records"][0]
    if (
        report["selected_source_candidates"] != 1
        or report["b0_wire_exports"] != 0
        or report["b1_wire_exports"] != 0
        or report["service_feature_fit_promotions"] != 0
        or catalog["evidence_kind"] != "authored_regression_fixture"
        or row["facts"]["volume_ml"] != 500
        or row["facts"]["abv_percent"] != 5
        or row["original_source_holds"] != ["mixed_brand_and_container_types"]
        or row["backend_product_id"] is not None
        or json.loads((output / "receipt.json").read_text())["completed"] is not True
    ):
        raise RuntimeError("The installed wheel violated source curation or business-ID isolation")
    smoke_business_export(python, work, manifest, raw, receipt, curation, catalog)
