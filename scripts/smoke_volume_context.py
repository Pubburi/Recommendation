"""Exercise installed-wheel context preparation with authored facts, never external data."""

import hashlib
import json
import subprocess
from pathlib import Path


def authored_inputs(work: Path) -> tuple[Path, dict]:
    """Only authored shapes; expected 330/20000mL is declared independently of the CLI."""

    def write(name, value):
        path = work / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def snak(prop, datatype, value):
        return {
            "property": prop,
            "datatype": datatype,
            "snaktype": "value",
            "datavalue": {
                "type": "quantity" if datatype == "quantity" else "wikibase-entityid",
                "value": value,
            },
        }

    def item(qid):
        return {"id": qid, "entity-type": "item", "numeric-id": int(qid[1:])}

    claims = []
    for suffix, context, amount in (("small", "Q10", "+0.33"), ("large", "Q11", "+20")):
        claims.append(
            {
                "id": "Q1$" + suffix,
                "rank": "normal",
                "mainsnak": snak(
                    "P2234",
                    "quantity",
                    {"amount": amount, "unit": "http://www.wikidata.org/entity/Q11582"},
                ),
                "qualifiers": {"P518": [snak("P518", "wikibase-item", item(context))]},
                "qualifiers-order": ["P518"],
            }
        )
    source = write(
        "authored-volume-family.json",
        {
            "success": 1,
            "entities": {
                "Q1": {
                    "id": "Q1",
                    "type": "item",
                    "lastrevid": 7,
                    "labels": {"en": {"value": "Authored family"}},
                    "claims": {"P2234": claims},
                }
            },
        },
    )
    definitions = write(
        "authored-volume-contexts.json",
        {
            "success": 1,
            "entities": {
                qid: {
                    "id": qid,
                    "type": "item",
                    "lastrevid": 8,
                    "labels": {"en": {"value": label}},
                    "claims": {},
                }
                for qid, label in (
                    ("Q10", "Authored small context"),
                    ("Q11", "Authored large context"),
                )
            },
        },
    )
    return source, {"context_input": definitions}


def smoke_volume_context(python: Path, work: Path, manifest: Path) -> None:
    source, inputs = authored_inputs(work)
    inputs["input"] = source

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    for name, ids in (("input", ["Q1"]), ("context_input", ["Q10", "Q11"])):
        output = work / ".pubburi" / ("volume-" + name)
        subprocess.run(
            [
                str(python),
                "-I",
                "-m",
                "pubburi_recommendation.wikidata_collect",
                "--manifest",
                str(manifest),
                "--ids",
                *ids,
                "--snapshot",
                str(inputs[name]),
                "--output-dir",
                str(output),
            ],
            cwd=work,
            check=True,
            timeout=10,
            stdout=subprocess.DEVNULL,
        )
        inputs["receipt" if name == "input" else "context_receipt"] = output / "receipt.json"
    review = work / "authored-volume-review.json"
    review.write_text(
        json.dumps(
            {
                "input_sha256": sha(source),
                "catalog_mode": "demo",
                "records": {
                    "Q1": {
                        "kind": "product_family",
                        "evidence_url": "https://example.invalid/authored",
                    }
                },
            }
        )
    )
    inputs["review"] = review
    spec = {
        "schema_version": 1,
        "evidence_kind": "authored_regression_fixture",
        "manifest_sha256": sha(manifest),
        **{key + "_sha256": sha(path) for key, path in inputs.items()},
        "family_groups": {"Q1": "authored-family"},
        "source_revisions": {"Q1": 7},
        "contexts": {
            qid: {
                "revision": 8,
                "label": label,
                "scope": "volume_context_only",
                "rationale": "Authored context only, not a real package/SKU.",
            }
            for qid, label in (("Q10", "Authored small context"), ("Q11", "Authored large context"))
        },
        "expected_observations": {
            "Q1$small": {"source_record_id": "Q1", "context_id": "Q10", "volume_ml": "330"},
            "Q1$large": {"source_record_id": "Q1", "context_id": "Q11", "volume_ml": "20000"},
        },
    }
    spec_path = work / "authored-volume-spec.json"
    spec_path.write_text(json.dumps(spec))
    output = work / ".pubburi" / "volume-observations.json"
    command = [
        str(python),
        "-I",
        "-m",
        "pubburi_recommendation.volume_context",
        "--manifest",
        str(manifest),
        "--spec",
        str(spec_path),
        "--output",
        str(output),
    ]
    for name, path in inputs.items():
        command.extend(["--" + name.replace("_", "-"), str(path)])
    subprocess.run(command, cwd=work, check=True, timeout=10, stdout=subprocess.DEVNULL)
    result = json.loads(output.read_text())
    if (
        result["preserved_observations"] != 2
        or result["held_observations"] != 0
        or result["families"][0]["volume_ml"] is not None
        or result["model_fit_performed"]
        or result["backend_mappings_created"] != 0
    ):
        raise RuntimeError(
            "Installed wheel violated the source volume-context observation boundary"
        )
    # A stale authority must fail without publishing an output or reflecting source data.
    spec["context_receipt_sha256"] = "f" * 64
    spec_path.write_text(json.dumps(spec))
    failed = work / ".pubburi" / "volume-rejected.json"
    command[command.index("--output") + 1] = str(failed)
    rejection = subprocess.run(
        command, cwd=work, check=False, timeout=10, capture_output=True, text=True
    )
    if (
        rejection.returncode != 2
        or failed.exists()
        or rejection.stderr != "volume_context_preparation_failed\n"
    ):
        raise RuntimeError("Installed wheel accepted a mismatched volume-context authority")
