"""Installed P3962 metadata/curation checks preserve barcode strings and collision holds."""

import copy
import json

from smoke_source_relations import run, sha, write


def smoke_gtin_metadata(python, work, manifest, raw, curation):
    for fault in ("property", "datatype", "collision"):
        payload = json.loads(raw.read_text())
        if fault == "collision":
            other = copy.deepcopy(payload["entities"]["Q1"])
            other.update(id="Q2", lastrevid=8)
            other["claims"]["P3962"][0]["mainsnak"]["datavalue"]["value"] = "00000012345670"
            other["claims"]["P3962"][0]["mainsnak"]["property"] = "P31"
            payload["entities"]["Q2"] = other
        else:
            payload["entities"]["Q1"]["claims"]["P3962"][0]["mainsnak"][fault] = (
                "P31" if fault == "property" else "wikibase-item"
            )
        source = write(work / ("gtin-" + fault + ".json"), payload)
        collected = work / ".pubburi" / ("gtin-" + fault + "-collection")
        run(
            python,
            work,
            "wikidata_collect",
            [
                "--manifest",
                manifest,
                "--ids",
                *sorted(payload["entities"]),
                "--snapshot",
                source,
                "--output-dir",
                collected,
            ],
        )
        audited = work / ".pubburi" / ("gtin-" + fault + "-audit")
        run(
            python,
            work,
            "package_identity_audit",
            [
                "--manifest",
                manifest,
                "--input",
                source,
                "--receipt",
                collected / "receipt.json",
                "--evidence-kind",
                "authored_regression_fixture",
                "--output-dir",
                audited,
            ],
        )
        rows = json.loads((audited / "package-records.json").read_text())
        row = rows[1 if fault == "collision" else 0]
        gtin = row["gtin_claims"][0]
        if (
            gtin["value"] != ("00000012345670" if fault == "collision" else "12345670")
            or not gtin["check_digit_valid"]
            or gtin["comparison_key_14"] != "00000012345670"
            or not gtin["structurally_usable"]
            or gtin["usable_without_context"]
            or gtin["issue"] != "gtin_statement_requires_review"
        ):
            raise RuntimeError(
                "Installed GTIN metadata guard changed integrity or authorized a conflict"
            )
        if fault == "collision" and (
            json.loads((audited / "audit-report.json").read_text())["shared_identifier_groups"] != 1
            or any(
                "identifier_shared_across_source_items" not in value["hold_reasons"]
                for value in rows
            )
        ):
            raise RuntimeError("Installed GTIN metadata filtering hid shared-identifier evidence")
        checked = json.loads(curation.read_text())
        checked.update(input_sha256=sha(source), receipt_sha256=sha(collected / "receipt.json"))
        checked_path = write(work / ("gtin-" + fault + "-curation.json"), checked)
        destination = work / ".pubburi" / ("gtin-" + fault + "-must-not-curate")
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
            raise RuntimeError(
                "Installed curation scope overrode invalid GTIN metadata or collisions"
            )
