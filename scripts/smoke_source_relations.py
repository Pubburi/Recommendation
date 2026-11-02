"""Installed offline relation faults: accepted receipts never authorize contradictory facts."""

import copy
import hashlib
import json
import math
import subprocess


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def run(python, work, module, arguments, *, expected=0):
    result = subprocess.run(
        [str(python), "-I", "-m", "pubburi_recommendation." + module, *map(str, arguments)],
        cwd=work,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != expected:
        raise RuntimeError("Installed relation integrity CLI violated its exit contract")
    return result


def smoke_family_relations(python, work, manifest, raw, review, spec):
    for prop, field, token in (
        ("P31", "instance_of_ids", "instance_of:Q10"),
        ("P176", "producer_ids", "producer:Q20"),
    ):
        for fault in ("property", "entity-type"):
            name = "relation-" + prop.lower() + "-" + fault
            payload = json.loads(raw.read_text())
            snak = payload["entities"]["Q1"]["claims"][prop][0]["mainsnak"]
            if fault == "property":
                snak["property"] = "P176" if prop == "P31" else "P31"
            else:
                snak["datavalue"]["value"]["entity-type"] = "property"
            source = write(work / (name + ".json"), payload)
            collected = work / ".pubburi" / (name + "-collection")
            run(
                python,
                work,
                "wikidata_collect",
                [
                    "--manifest",
                    manifest,
                    "--ids",
                    "Q1",
                    "Q2",
                    "Q3",
                    "--snapshot",
                    source,
                    "--output-dir",
                    collected,
                ],
            )
            rows = json.loads((collected / "normalized-records.json").read_text())
            if (
                rows[0][field]
                or not json.loads((collected / "receipt.json").read_text())["accepted"]
            ):
                raise RuntimeError("Installed collector inferred contradictory item relations")
            checked = json.loads(review.read_text())
            checked["input_sha256"] = sha(source)
            changed_review = write(work / (name + "-review.json"), checked)
            changed_spec = json.loads(spec.read_text())
            changed_spec.update(
                input_sha256=sha(source),
                receipt_sha256=sha(collected / "receipt.json"),
                review_sha256=sha(changed_review),
            )
            changed_spec_path = write(work / (name + "-spec.json"), changed_spec)
            destination = work / ".pubburi" / (name + "-must-not-fit.json")
            arguments = [
                "--manifest",
                manifest,
                "--input",
                source,
                "--receipt",
                collected / "receipt.json",
                "--review",
                changed_review,
                "--spec",
                changed_spec_path,
                "--output",
                destination,
            ]
            failure = run(python, work, "source_family_experiment", arguments, expected=2)
            if destination.exists() or failure.stderr.strip() != (
                "Source family experiment failed: manual_facts_conflict_with_reviewed_source"
            ):
                raise RuntimeError("Installed family fit accepted contradictory declared relations")
            honest = copy.deepcopy(changed_spec)
            honest["expected_facts"]["Q1"][field] = []
            honest_path = write(work / (name + "-honest-spec.json"), honest)
            destination = destination.with_name(name + "-honest-fit.json")
            arguments[-3], arguments[-1] = honest_path, destination
            run(python, work, "source_family_experiment", arguments)
            parameters = json.loads(destination.read_text())["fitted_parameters"]
            idf = dict(zip(parameters["vocabulary"], parameters["idf"], strict=True))
            if (
                (prop == "P31" and token in idf)
                or (prop == "P176" and not math.isclose(idf[token], math.log(3 / 2) + 1))
                or parameters["numeric_fit"]["abv_percent"]["observed_training_values"] != 2
            ):
                raise RuntimeError("Installed honest unknowns changed unaffected fit evidence")


def smoke_package_relations(python, work, manifest, raw, curation):
    for fault in ("container-property", "neighbor-brand-type"):
        payload = json.loads(raw.read_text())
        statements = payload["entities"]["Q1"]["claims"]["P31"]
        if fault == "container-property":
            del statements[1:]
            statements[0]["mainsnak"]["property"] = "P176"
        else:
            statements[1]["mainsnak"]["datavalue"]["type"] = "string"
        source = write(work / (fault + ".json"), payload)
        collected = work / ".pubburi" / (fault + "-collection")
        run(
            python,
            work,
            "wikidata_collect",
            [
                "--manifest",
                manifest,
                "--ids",
                "Q1",
                "--snapshot",
                source,
                "--output-dir",
                collected,
            ],
        )
        checked = json.loads(curation.read_text())
        checked.update(input_sha256=sha(source), receipt_sha256=sha(collected / "receipt.json"))
        checked_path = write(work / (fault + "-curation.json"), checked)
        destination = work / ".pubburi" / (fault + "-must-not-curate")
        failure = run(
            python,
            work,
            "source_catalog",
            [
                "--manifest",
                manifest,
                "--input",
                source,
                "--receipt",
                collected / "receipt.json",
                "--curation",
                checked_path,
                "--output-dir",
                destination,
            ],
            expected=2,
        )
        if destination.exists() or failure.stderr.strip() != (
            "Source catalog curation failed: curation_cannot_override_unresolved_source_hold"
        ):
            raise RuntimeError("Installed mixed-type scope bypassed malformed P31 source holds")
