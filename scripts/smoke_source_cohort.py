"""Check installed unseen-producer cohort CLI using separately authored source snapshots."""

import copy
import hashlib
import json
import subprocess


def smoke_source_cohort(python, work, manifest, raw, receipt, review, facts):
    def write(name, value):
        path = work / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def relation(qid):
        return {
            "rank": "normal",
            "mainsnak": {
                "snaktype": "value",
                "datavalue": {
                    "type": "wikibase-entityid",
                    "value": {"id": qid},
                },
            },
        }

    entity = copy.deepcopy(json.loads(raw.read_text())["entities"]["Q3"])
    entity.update(id="Q4", lastrevid=8)
    entity["claims"]["P31"] = [relation("Q11")]
    entity["claims"]["P176"] = [relation("Q21")]
    second = write("authored-other-producer.json", {"success": 1, "entities": {"Q4": entity}})
    collection = work / ".pubburi" / "cohort-other-collection"
    subprocess.run(
        [
            str(python),
            "-I",
            "-m",
            "pubburi_recommendation.wikidata_collect",
            "--manifest",
            str(manifest),
            "--ids",
            "Q4",
            "--snapshot",
            str(second),
            "--output-dir",
            str(collection),
        ],
        cwd=work,
        check=True,
        timeout=10,
        stdout=subprocess.DEVNULL,
    )
    second_receipt = collection / "receipt.json"
    second_review = write(
        "authored-other-producer-review.json",
        {
            "input_sha256": sha(second),
            "catalog_mode": "demo",
            "records": {
                "Q4": {"kind": "product_family", "evidence_url": "https://example.org/authored"}
            },
        },
    )
    frozen_facts = {qid: facts[qid] for qid in ("Q1", "Q2")}
    frozen_facts["Q4"] = {**facts["Q3"], "instance_of_ids": ["Q11"], "producer_ids": ["Q21"]}
    bindings = []
    for name, source, collected, checked, ids in (
        ("known", raw, receipt, review, ["Q1", "Q2"]),
        ("unseen", second, second_receipt, second_review, ["Q4"]),
    ):
        bindings.append(
            {
                "snapshot_id": name,
                "input_sha256": sha(source),
                "receipt_sha256": sha(collected),
                "review_sha256": sha(checked),
                "selected_ids": ids,
            }
        )
    spec = write(
        "authored-cohort-spec.json",
        {
            "schema_version": 1,
            "experiment_id": "authored-installed-cohort",
            "evidence_kind": "authored_regression_fixture",
            "data_kind": "reviewed_source_product_families",
            "manifest_sha256": sha(manifest),
            "snapshot_bindings": bindings,
            "split_policy": "unseen_producer",
            "family_groups": {"Q1": "family-a", "Q2": "family-b", "Q4": "family-c"},
            "fit_groups": ["family-a", "family-b"],
            "transform_groups": ["family-c"],
            "expected_facts": frozen_facts,
            "retrieval_cases": [
                {
                    "case_id": "authored-cross-producer",
                    "query_id": "Q4",
                    "candidate_ids": ["Q1", "Q2"],
                    "relevant_ids": ["Q2"],
                    "cutoffs": [1, 2],
                    "fact_basis": "Authored exact Q11 relation, not service quality.",
                }
            ],
        },
    )
    output = work / ".pubburi" / "cohort-fit.json"
    subprocess.run(
        [
            str(python),
            "-I",
            "-m",
            "pubburi_recommendation.source_family_cohort",
            "--manifest",
            str(manifest),
            "--spec",
            str(spec),
            "--output",
            str(output),
            "--snapshot",
            "known",
            str(raw),
            str(receipt),
            str(review),
            "--snapshot",
            "unseen",
            str(second),
            str(second_receipt),
            str(second_review),
        ],
        cwd=work,
        check=True,
        timeout=60,
        stdout=subprocess.DEVNULL,
    )
    result = json.loads(output.read_text())
    if (
        not result["passed_contract"]
        or result["fit_records"] != 2
        or result["transform_records"] != 1
        or result["cohort"]["producer_overlap"] != 0
        or result["cohort"]["selected_producers"] != 2
        or result["transformed"][0]["unknown_tokens"] != ["producer:Q21"]
        or len(result["hashes"]["snapshots"]) != 2
        or result["ranking_metrics"]["positive_label_queries"] != 1
    ):
        raise RuntimeError("Installed cohort violated separate authorities or producer holdout")
