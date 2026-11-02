"""Exercise fixed SVD CLI/replay/leakage and authority failure in a runtime-only wheel."""

import copy
import hashlib
import json
import math
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def smoke_source_comparison(python, work, cohort_arguments):
    def write(name, value):
        path = work / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def run(module, arguments, *, success=True):
        result = subprocess.run(
            [str(python), "-I", "-m", "pubburi_recommendation." + module, *arguments],
            cwd=work,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != (0 if success else 2):
            raise RuntimeError("Installed representation comparison violated its exit contract")
        return result

    spec = Path(cohort_arguments[cohort_arguments.index("--spec") + 1])
    baseline = Path(cohort_arguments[cohort_arguments.index("--output") + 1])
    manifest = Path(cohort_arguments[cohort_arguments.index("--manifest") + 1])
    original = json.loads(baseline.read_text())
    original_sha = sha(baseline)
    config = {
        "schema_version": 1,
        "algorithm": "source-family-tfidf-svd-comparison-v1",
        "frozen_at_utc": datetime.now(UTC).isoformat(),
        "base_spec_sha256": sha(spec),
        "baseline_report_sha256": original_sha,
        "baseline_fingerprint": original["fit_fingerprint"],
        "evidence_kind": "authored_regression_fixture",
        "sklearn_version": original["sklearn_version"],
        "n_components": 1,
        "random_state": 0,
        "svd_algorithm": "randomized",
        "n_iter": 7,
        "n_oversamples": 10,
        "power_iteration_normalizer": "QR",
        "normalization": "l2_tfidf_then_l2_latent",
        "retrieval_case_ids": [row["case_id"] for row in original["ranking_metrics"]["cases"]],
        "predeclared_measurements": [
            "training_reconstruction_relative_frobenius_error",
            "training_retained_frobenius_energy_ratio",
            "training_explained_variance_ratio",
            "transform_zero_nonzero_latent_and_OOV_coverage",
            "same_frozen_fact_retrieval_complete_signed_cosine_rankings_and_positive_query_denominators",
        ],
        "decision_scope": "representation_adequacy_only_not_service_adoption_or_quality",
        "no_parameter_sweep_or_heldout_tuning": True,
    }
    config_path = write("authored-comparison.json", config)
    output = work / ".pubburi" / "source-comparison.json"
    arguments = list(cohort_arguments)
    arguments[arguments.index("--output") + 1] = str(output)
    arguments += ["--comparison-spec", str(config_path), "--baseline-report", str(baseline)]
    run("source_representation_comparison", arguments)
    result = json.loads(output.read_text())
    candidate = result["candidate"]
    if (
        result["baseline"] != original
        or sha(baseline) != original_sha
        or candidate["fit_records"] != 2
        or candidate["transform_records"] != 1
        or candidate["latent_dimensions"] != 1
        or candidate["transform_coverage"]["nonzero_latent_vectors"] != 1
        or candidate["ranking_metrics"]["positive_label_queries"] != 1
        or not math.isfinite(
            candidate["training_measurements"]["reconstruction_relative_frobenius_error"]
        )
        or candidate["adoption"] != "not_adopted_by_offline_comparison"
    ):
        raise RuntimeError("Installed comparison changed its baseline, fit or evidence scope")
    replay = output.with_name("source-comparison-replay.json")
    replay_arguments = list(arguments)
    replay_arguments[replay_arguments.index("--output") + 1] = str(replay)
    run("source_representation_comparison", replay_arguments)
    if output.read_bytes() != replay.read_bytes():
        raise RuntimeError("Installed comparison was not reproducible under its frozen protocol")

    # A separate authored held-out mutation changes its real raw/receipt/review authorities.
    # Its unseen class/ABV must change only transform outputs, never candidate fit parameters.
    unseen_index = cohort_arguments.index("unseen")
    unseen = Path(cohort_arguments[unseen_index + 1])
    payload = json.loads(unseen.read_text())
    payload["entities"]["Q4"]["claims"]["P31"][0]["mainsnak"]["datavalue"]["value"]["id"] = "Q999"
    payload["entities"]["Q4"]["claims"]["P2665"][0]["mainsnak"]["datavalue"]["value"]["amount"] = (
        "100"
    )
    altered_raw = write("authored-comparison-heldout.json", payload)
    collection = work / ".pubburi" / "comparison-heldout-collection"
    run(
        "wikidata_collect",
        [
            "--manifest",
            str(manifest),
            "--ids",
            "Q4",
            "--snapshot",
            str(altered_raw),
            "--output-dir",
            str(collection),
        ],
    )
    altered_receipt = collection / "receipt.json"
    review = json.loads(Path(cohort_arguments[unseen_index + 3]).read_text())
    review["input_sha256"] = sha(altered_raw)
    altered_review = write("authored-comparison-heldout-review.json", review)
    changed = json.loads(spec.read_text())
    binding = next(row for row in changed["snapshot_bindings"] if row["snapshot_id"] == "unseen")
    binding.update(
        input_sha256=sha(altered_raw),
        receipt_sha256=sha(altered_receipt),
        review_sha256=sha(altered_review),
    )
    changed["expected_facts"]["Q4"].update(instance_of_ids=["Q999"], abv_percent=100)
    changed["retrieval_cases"][0].update(
        relevant_ids=[], fact_basis="Authored Q999 is absent from both training families."
    )
    altered_spec = write("authored-comparison-heldout-spec.json", changed)
    altered_baseline = work / ".pubburi" / "comparison-heldout-baseline.json"
    changed_arguments = list(cohort_arguments)
    changed_arguments[changed_arguments.index("--spec") + 1] = str(altered_spec)
    changed_arguments[changed_arguments.index("--output") + 1] = str(altered_baseline)
    changed_arguments[unseen_index + 1 : unseen_index + 4] = map(
        str, (altered_raw, altered_receipt, altered_review)
    )
    run("source_family_cohort", changed_arguments)
    new_config = copy.deepcopy(config)
    new_config.update(
        base_spec_sha256=sha(altered_spec), baseline_report_sha256=sha(altered_baseline)
    )
    altered_config = write("authored-comparison-heldout-config.json", new_config)
    altered_output = work / ".pubburi" / "comparison-heldout-result.json"
    changed_arguments[changed_arguments.index("--output") + 1] = str(altered_output)
    changed_arguments += [
        "--comparison-spec",
        str(altered_config),
        "--baseline-report",
        str(altered_baseline),
    ]
    run("source_representation_comparison", changed_arguments)
    transformed = json.loads(altered_output.read_text())["candidate"]
    if (
        transformed["fitted_parameters"] != candidate["fitted_parameters"]
        or transformed["fit_fingerprint"] != candidate["fit_fingerprint"]
        or transformed["transform_coverage"]["zero_latent_vectors"] != 1
        or transformed["ranking_metrics"]["positive_label_queries"] != 0
        or transformed["ranking_metrics"]["omitted_no_positive_queries"] != 1
    ):
        raise RuntimeError("Installed comparison leaked held-out facts or hid no-positive queries")
    # Stale source bytes must fail before any new report; keep all earlier reports intact.
    altered_raw.write_text(altered_raw.read_text() + " ")
    rejected = altered_output.with_name("comparison-must-not-exist.json")
    changed_arguments[changed_arguments.index("--output") + 1] = str(rejected)
    failure = run("source_representation_comparison", changed_arguments, success=False)
    if (
        rejected.exists()
        or failure.stderr.strip()
        != "Source representation comparison failed: cohort_snapshot_authority_hash_mismatch"
        or sha(baseline) != original_sha
    ):
        raise RuntimeError("Installed comparison accepted stale authority or damaged its baseline")
