"""Run source-family fit through a runtime-only installed wheel using authored records."""

import hashlib
import json
import subprocess
from pathlib import Path

from smoke_source_catalog import smoke_source_catalog


def smoke_source_family(python: Path, work: Path, manifest: Path) -> None:
    def write(name, payload):
        path = work / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    facts = {
        "Q1": {
            "instance_of_ids": ["Q10"],
            "producer_ids": ["Q20"],
            "abv_percent": 5,
            "volume_ml": None,
        },
        "Q2": {
            "instance_of_ids": ["Q11"],
            "producer_ids": ["Q20"],
            "abv_percent": 15,
            "volume_ml": None,
        },
        "Q3": {
            "instance_of_ids": ["Q99"],
            "producer_ids": ["Q20"],
            "abv_percent": 25,
            "volume_ml": None,
        },
    }
    entities = {}
    for qid, row in facts.items():
        entities[qid] = {
            "id": qid,
            "type": "item",
            "lastrevid": 7,
            "labels": {"mul": {"value": "Authored family, not actual source data"}},
            "claims": {
                "P31": [{"mainsnak": {"datavalue": {"value": {"id": row["instance_of_ids"][0]}}}}],
                "P176": [{"mainsnak": {"datavalue": {"value": {"id": "Q20"}}}}],
                "P2665": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "snaktype": "value",
                            "datavalue": {
                                "value": {
                                    "amount": str(row["abv_percent"]),
                                    "unit": "http://www.wikidata.org/entity/Q2080811",
                                }
                            },
                        },
                    }
                ],
            },
        }
    # A self-authored checksum example, not a GS1 assignment or actual source product.
    entities["Q1"]["claims"]["P3962"] = [
        {
            "rank": "normal",
            "mainsnak": {
                "snaktype": "value",
                "datavalue": {"type": "string", "value": "12345670"},
            },
        }
    ]
    raw = write("authored-families.json", {"success": 1, "entities": entities})
    collection = work / ".pubburi" / "family-collection"
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
            "Q2",
            "Q3",
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
    review = write(
        "authored-family-review.json",
        {
            "input_sha256": sha(raw),
            "catalog_mode": "demo",
            "records": {
                qid: {"kind": "product_family", "evidence_url": "https://example.org/authored"}
                for qid in facts
            },
        },
    )
    spec = write(
        "authored-family-spec.json",
        {
            "schema_version": 1,
            "experiment_id": "authored-wheel-family-fit",
            "evidence_kind": "authored_regression_fixture",
            "data_kind": "reviewed_source_product_families",
            "input_sha256": sha(raw),
            "review_sha256": sha(review),
            "receipt_sha256": sha(receipt),
            "manifest_sha256": sha(manifest),
            "family_groups": {"Q1": "family-a", "Q2": "family-b", "Q3": "family-c"},
            "fit_groups": ["family-a", "family-b"],
            "transform_groups": ["family-c"],
            "expected_facts": facts,
            "retrieval_cases": [
                {
                    "case_id": "authored-unseen-style",
                    "query_id": "Q3",
                    "candidate_ids": ["Q1", "Q2"],
                    "relevant_ids": [],
                    "cutoffs": [1, 2],
                    "fact_basis": "Authored Q99 differs from both declared candidate classes.",
                }
            ],
        },
    )
    output = work / ".pubburi" / "family-fit.json"
    command = [str(python), "-I", "-m", "pubburi_recommendation.source_family_experiment"]
    for name, path in {
        "manifest": manifest,
        "input": raw,
        "receipt": receipt,
        "review": review,
        "spec": spec,
        "output": output,
    }.items():
        command += ["--" + name, str(path)]
    subprocess.run(command, cwd=work, check=True, timeout=60, stdout=subprocess.DEVNULL)
    report = json.loads(output.read_text())
    if (
        not report["passed_contract"]
        or report["fit_records"] != 2
        or report["transform_records"] != 1
        or report["evidence_kind"] != "authored_regression_fixture"
        or report["fitted_parameters"]["vocabulary"]
        != ["instance_of:Q10", "instance_of:Q11", "producer:Q20"]
        or report["transformed"][0]["unknown_tokens"] != ["instance_of:Q99"]
        or report["fitted_parameters"]["numeric_fit"]["volume_ml"]["active"]
        or report["ranking_metrics"]["status"] != "not_calculated"
        or report["ranking_metrics"]["query_count"] != 1
        or report["ranking_metrics"]["positive_label_queries"] != 0
        or report["ranking_metrics"]["omitted_no_positive_queries"] != 1
    ):
        raise RuntimeError("The installed wheel violated source-family fit/transform boundaries")
    # Inspect an independently authored positive ranking, without fitting or synthesizing gold.
    subprocess.run(
        [
            str(python),
            "-I",
            "-c",
            "from pubburi_recommendation.source_family_evaluation import "
            "FamilyRetrievalCase, inspect_retrieval; "
            "case=FamilyRetrievalCase(case_id='authored-positive',query_id='Q3',"
            "candidate_ids=['Q1','Q2'],relevant_ids=['Q2'],cutoffs=[1],"
            "fact_basis='Authored exact class relation, not real source observations.'); "
            "result=inspect_retrieval(case,[{'source_record_id':'Q2','score':1.0},"
            "{'source_record_id':'Q1','score':0.0}]); "
            "assert result['reference_metrics']['at_k']['1']=={'recall':0,'ndcg':0}; "
            "assert result['representation_metrics']['at_k']['1']=={'recall':1,'ndcg':1}",
        ],
        cwd=work,
        check=True,
        timeout=10,
        stdout=subprocess.DEVNULL,
    )
    package_output = work / ".pubburi" / "package-audit"
    subprocess.run(
        [
            str(python),
            "-I",
            "-m",
            "pubburi_recommendation.package_identity_audit",
            "--manifest",
            str(manifest),
            "--input",
            str(raw),
            "--receipt",
            str(receipt),
            "--evidence-kind",
            "authored_regression_fixture",
            "--output-dir",
            str(package_output),
        ],
        cwd=work,
        check=True,
        timeout=10,
        stdout=subprocess.DEVNULL,
    )
    package_report = json.loads((package_output / "audit-report.json").read_text())
    package_receipt = json.loads((package_output / "receipt.json").read_text())
    if (
        package_report["entities"] != 3
        or package_report["checksum_valid_claims"] != 1
        or package_report["package_field_combination_entities"] != 0
        or package_report["backend_mappings_approved"] != 0
        or package_report["feature_fit_promotions"] != 0
        or package_report["evidence_kind"] != "authored_regression_fixture"
        or package_receipt["completed"] is not True
    ):
        raise RuntimeError("The installed wheel confused package evidence with SKU approval")
    smoke_source_catalog(python, work, manifest, entities["Q1"])
