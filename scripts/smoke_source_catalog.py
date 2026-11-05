"""Run source-container curation from an isolated wheel using authored source shapes."""

import copy
import csv
import hashlib
import io
import json
import subprocess
from pathlib import Path

from smoke_business_export import smoke_business_export
from smoke_gtin_metadata import smoke_gtin_metadata
from smoke_source_relations import smoke_package_relations


def smoke_at_source(python: Path, work: Path, manifest: Path) -> None:
    """Installed audit -> authored fact curation -> unchanged B1, without live acquisition."""

    def write(name, value):
        path = work / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(
        [
            "제품명",
            "제품소개",
            "알콜도수1",
            "알콜도수2",
            "알콜도수3",
            "용량1",
            "용량2",
            "용량3",
            "성분1",
            "성분2",
            "특이사항",
            "특징",
            "양조장",
            "양조장주소",
            "홈페이지주소",
            "수상내역",
        ]
    )
    writer.writerow(
        [
            "가상 원천",
            "제외할 소개",
            "0",
            "",
            "",
            "750",
            "",
            "",
            "",
            "",
            "",
            "",
            "가상 양조장",
            "",
            "",
            "",
        ]
    )
    raw = work / "authored-at.csv"
    raw.write_bytes(stream.getvalue().encode("cp949"))
    evidence = work / "authored-at-evidence.html"
    evidence.write_bytes(b"Authored category and zero ABV fact, not actual provider content")
    receipt = write(
        "authored-at-receipt.json",
        {
            "schema_version": 1,
            "evidence_kind": "authored_regression_fixture",
            "dataset_id": "15048755",
            "source_version": "20260731",
            "observed_at_utc": "2026-11-05T00:00:00Z",
            "source_sha256": sha(raw),
            "source_bytes": raw.stat().st_size,
            "http_status": 200,
            "normal_public_rate_guard_passed": True,
            "images_fetched": False,
        },
    )
    review = write(
        "authored-at-review.json",
        {
            "schema_version": 1,
            "algorithm": "at-reviewed-source-facts-v1",
            "input_sha256": sha(raw),
            "receipt_sha256": sha(receipt),
            "manifest_sha256": sha(manifest),
            "source_version": "20260731",
            "records": [
                {
                    "row_number": 1,
                    "expected_label": "가상 원천",
                    "expected_producer": "가상 양조장",
                    "category": "과실주",
                    "abv_percent": 0.0,
                    "abv_unit": "%",
                    "evidence_url": "https://thesool.com/front/publication/M000000066/view.do?publicationId=fixture",
                    "evidence_sha256": sha(evidence),
                    "review_note": "Authored regression only",
                }
            ],
        },
    )
    output = work / ".pubburi" / "at-curated"
    command = [
        str(python),
        "-I",
        "-m",
        "pubburi_recommendation.catalog_audit",
        "--manifest",
        str(manifest),
        "--input",
        str(raw),
        "--receipt",
        str(receipt),
        "--review",
        str(review),
        "--fact-evidence",
        str(evidence),
        "--output-dir",
        str(output),
    ]
    subprocess.run(command, cwd=work, check=True, timeout=10, stdout=subprocess.DEVNULL)
    probe = (
        "import json,sys; from pathlib import Path; "
        "from pubburi_recommendation.content_model import "
        "ContentProduct,ContentProfile,FittedContentModel; "
        "from pubburi_recommendation.baseline import Constraints; "
        "rows=json.loads(Path(sys.argv[1]).read_text()); r=rows[0]; "
        "assert r['abv_percent']==0 and r['volume_ml'] is r['taste_tags'] is None; "
        "assert r['backend_product_id'] is None and r['sku_group'] is None; "
        "p=ContentProduct(product_id=1,sku_group='explicit-offline-row',available=True,"
        "category=r['category'],abv_percent=r['abv_percent']); "
        "m=FittedContentModel.fit([p]); "
        "assert m.summary['numeric_fit']['abv_percent']['observed_count']==1; "
        "assert len(m.rank([p],ContentProfile(),Constraints(max_abv_percent=0)).items)==1; "
        "assert m.rank([p],ContentProfile()).fallback_reason=='no_supported_preferences'"
    )
    subprocess.run(
        [str(python), "-I", "-c", probe, str(output / "normalized-records.json")],
        cwd=work,
        check=True,
        timeout=20,
    )
    if (output / "b0-demo-request.json").exists():
        raise RuntimeError("Source rows must not automatically become service requests")
    raw.write_bytes(raw.read_bytes() + b"\n")
    changed = work / ".pubburi" / "at-changed"
    command[-1] = str(changed)
    rejected = subprocess.run(command, cwd=work, capture_output=True, timeout=10)
    if rejected.returncode != 2 or changed.exists():
        raise RuntimeError("Changed source bytes bypassed the installed receipt boundary")


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
    smoke_package_relations(python, work, manifest, raw, curation)
    smoke_gtin_metadata(python, work, manifest, raw, curation)
