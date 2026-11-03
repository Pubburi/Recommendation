"""Completed export consumption with authored authorities, no real data/network."""

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from test_family_browse_catalog import business, inputs

from pubburi_recommendation.business_export import ALGORITHM, ReviewedMapping, build_exports
from pubburi_recommendation.catalog_audit import AuditError, read_json
from pubburi_recommendation.catalog_authority import load_export_catalog
from pubburi_recommendation.checked_export import load_checked_export
from pubburi_recommendation.main import app
from pubburi_recommendation.reviewed_provider_acceptance import (
    ProviderSpec,
    inspect_response,
    loopback_base_url,
    prepare_cases,
)


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return path


@pytest.fixture
def bundle(tmp_path):
    paths, _ = inputs(tmp_path)
    manifest, raw, receipt, curation, review = paths
    catalog, _ = load_export_catalog(manifest, raw, receipt, curation, family_review=review)
    snapshot, mapping, now = business(catalog)
    snapshot_path = write(tmp_path / "snapshot.json", snapshot)
    _, snapshot_hash = read_json(snapshot_path)
    mapping["business_snapshot_sha256"] = snapshot_hash
    mapping_path = write(tmp_path / "mapping.json", mapping)
    _, mapping_hash = read_json(mapping_path)
    report, requests = build_exports(
        catalog, snapshot, snapshot_hash, ReviewedMapping.model_validate(mapping), now
    )
    report["mapping_sha256"] = mapping_hash
    folder = tmp_path / ".pubburi" / "export"
    folder.mkdir()
    for name, value in {"export-report.json": report, **requests}.items():
        write(folder / name, value)
    write(
        folder / "receipt.json",
        {
            "algorithm": ALGORITHM,
            "completed": True,
            "exported_products": 2,
            "snapshot_sha256": snapshot_hash,
            "mapping_sha256": mapping_hash,
        },
    )
    args = (folder, manifest, raw, receipt, curation, snapshot_path, mapping_path)
    return {
        "args": args,
        "family_review": review,
        "now": now,
        "requests": requests,
        "catalog": catalog,
        "snapshot": snapshot,
        "mapping": mapping,
        "export": folder,
    }


def load(bundle, **kwargs):
    return load_checked_export(*bundle["args"], family_review=bundle["family_review"], **kwargs)


def specification(bundle, checked):
    from pubburi_recommendation.content_model import FittedContentModel

    # Offline fit fingerprint binds the prior representation; expected facts/order below
    # are authored constants and are never produced by its scoring/filtering helpers.
    fingerprint = FittedContentModel.fit(checked.request.catalog).fingerprint
    keys = ["authored-family-q1", "authored-family-q2"]

    def case(provider):
        reference = provider in ("similar", "context", "feedback")
        items = keys[1:] if reference else keys
        return {
            "case_id": provider,
            "provider": provider,
            "profile": {} if reference else {"categories": ["맥주"], "preferred_abv_percent": 0},
            "reference_keys": keys[:1] if provider in ("similar", "context") else [],
            "positive_keys": keys[:1] if provider == "feedback" else [],
            "expected_eligible_keys": items,
            "expected_item_keys": items,
            "expected_comparisons": {k: keys[0] if reference else None for k in items},
            "expected_fallback": None,
            "expected_representation_fitted": True,
            "fact_basis": "Authored 0/10 ABV, explicit demo category/price, unknown volume/tags.",
        }

    return {
        "schema_version": 1,
        "experiment_id": "authored-checked-provider",
        "evidence_kind": "authored_regression_fixture",
        "source_catalog_sha256": checked.metadata["source_catalog_sha256"],
        "frozen_at_utc": datetime.now(UTC).isoformat(),
        "expected_model_fingerprint": fingerprint,
        "expected_facts": {
            k: {
                "available": True,
                "category": "맥주",
                "price_krw": 1000,
                "abv_percent": abv,
                "volume_ml": None,
                "sku_group": "authored-group-q" + str(i),
                "taste_tags": None,
                "aroma_tags": None,
            }
            for i, k, abv in ((1, keys[0], 0), (2, keys[1], 10))
        },
        "cases": [
            case(provider)
            for provider in ("content", "exploration", "similar", "context", "feedback")
        ],
    }


def test_exact_completed_bundle_loads_without_changes_and_mode_never_approves_service(bundle):
    before = {p.name: p.read_bytes() for p in bundle["export"].iterdir()}
    checked = load(bundle, now=bundle["now"])
    assert checked.request.model_dump() == bundle["requests"]["b1-demo-request.json"]
    assert checked.metadata["mode"] == "fresh_demo_snapshot"
    assert (
        checked.metadata["model_loaded"] is False
        and checked.metadata["service_catalog_approved"] is False
    )
    assert checked.metadata["current_business_revalidation_required"] is True
    assert {p.name: p.read_bytes() for p in bundle["export"].iterdir()} == before


def test_stale_normal_load_fails_but_explicit_replay_keeps_historical_identity(bundle):
    after = bundle["now"] + timedelta(seconds=301)
    with pytest.raises(AuditError, match="stale"):
        load(bundle, now=after)
    result = load(bundle, now=after, replay=True)
    assert result.metadata["mode"] == "historical_demo_replay"
    assert result.metadata["original_export_at_utc"] == bundle["now"].isoformat()
    assert result.metadata["service_catalog_approved"] is False


@pytest.mark.parametrize(
    "name", ["b0-demo-request.json", "b1-demo-request.json", "export-report.json", "receipt.json"]
)
def test_missing_or_noncanonical_artifact_bytes_cannot_be_consumed(bundle, name):
    p = bundle["export"] / name
    original = p.read_bytes()
    p.write_bytes(original + b" ")
    with pytest.raises(AuditError, match="bytes_conflict"):
        load(bundle, now=bundle["now"])
    p.unlink()
    with pytest.raises(AuditError, match="file_set"):
        load(bundle, now=bundle["now"])


@pytest.mark.parametrize("completed", [False, 1, "true", None])
def test_incomplete_or_coerced_receipt_is_not_approval(bundle, completed):
    p = bundle["export"] / "receipt.json"
    d = json.loads(p.read_text())
    d["completed"] = completed
    write(p, d)
    with pytest.raises(AuditError, match="completed_receipt"):
        load(bundle, now=bundle["now"])


@pytest.mark.parametrize("name", ["b0-demo-request.json", "b1-demo-request.json"])
def test_changed_request_catalog_cannot_borrow_original_receipt(bundle, name):
    p = bundle["export"] / name
    d = json.loads(p.read_text())
    d["catalog"][0]["price_krw"] = 0
    write(p, d)
    with pytest.raises(AuditError, match="bytes_conflict"):
        load(bundle, now=bundle["now"])


def test_changed_mapping_snapshot_and_source_remain_authority_gates(bundle):
    snapshot = bundle["args"][5]
    old = snapshot.read_bytes()
    d = json.loads(old)
    d["records"][0]["product"]["data"]["price"] = 0
    write(snapshot, d)
    with pytest.raises(AuditError, match="hash_mismatch"):
        load(bundle, now=bundle["now"])
    snapshot.write_bytes(old)
    raw = bundle["args"][2]
    raw.write_bytes(raw.read_bytes() + b" ")
    with pytest.raises(AuditError):
        load(bundle, now=bundle["now"], replay=True)


def test_replay_cannot_launder_export_that_was_stale_or_future_when_recorded(bundle):
    p = bundle["export"] / "export-report.json"
    d = json.loads(p.read_text())
    d["evaluated_at_utc"] = (bundle["now"] + timedelta(seconds=301)).isoformat()
    write(p, d)
    with pytest.raises(AuditError, match="stale"):
        load(bundle, now=bundle["now"] + timedelta(seconds=302), replay=True)
    with pytest.raises(AuditError, match="future"):
        load(bundle, now=bundle["now"], replay=True)


def test_extra_and_symlink_files_are_not_a_completed_export(bundle, tmp_path):
    extra = bundle["export"] / "request.tmp"
    extra.touch()
    with pytest.raises(AuditError, match="file_set"):
        load(bundle, now=bundle["now"])
    extra.unlink()
    target = tmp_path / "elsewhere.json"
    p = bundle["export"] / "b1-demo-request.json"
    target.write_bytes(p.read_bytes())
    p.unlink()
    p.symlink_to(target)
    with pytest.raises(AuditError, match="regular_artifact"):
        load(bundle, now=bundle["now"])


def test_same_checked_catalog_runs_all_existing_five_b1_adapters_with_independent_facts(bundle):
    checked = load(bundle, now=bundle["now"])
    spec = ProviderSpec.model_validate(specification(bundle, checked))
    with TestClient(app) as client:
        for case, body, constraints in prepare_cases(spec, checked, datetime.now(UTC)):
            response = client.post("/v1/recommendations/" + case.provider, json=body)
            assert response.status_code == 200
            assert inspect_response(case, body, constraints, response.json(), checked, spec) == []


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(eligible_count=0),
        lambda d: d.update(model_fingerprint="0" * 64),
        lambda d: d["items"][0].update(product_id=999),
        lambda d: d["items"][0]["explanation"]["comparison"].update(
            kind="reference_product", product_id=38
        ),
        lambda d: d["items"][0]["explanation"]["score_evidence"][0].update(target_value="invented"),
        lambda d: d["items"][0]["explanation"]["filter_evidence"][0].update(actual_value=False),
        lambda d: d["items"][0]["contributions"][0].update(contribution=0),
        lambda d: d["items"][0]["explanation"].update(score_evidence_truncated=True),
        lambda d: d["items"][0]["explanation"].update(basis="deterministic_baseline"),
    ],
)
def test_independent_inspector_rejects_corrupted_actual_provider_results(bundle, mutation):
    checked = load(bundle, now=bundle["now"])
    spec = ProviderSpec.model_validate(specification(bundle, checked))
    case, body, constraints = prepare_cases(spec, checked, datetime.now(UTC))[0]
    with TestClient(app) as client:
        d = client.post("/v1/recommendations/content", json=body).json()
    mutation(d)
    assert inspect_response(case, body, constraints, d, checked, spec)


def test_false_frozen_facts_or_eligibility_fail_before_any_http(bundle):
    checked = load(bundle, now=bundle["now"])
    d = specification(bundle, checked)
    d["expected_facts"]["authored-family-q1"]["abv_percent"] = 1
    with pytest.raises(AuditError, match="product_fact"):
        prepare_cases(ProviderSpec.model_validate(d), checked, datetime.now(UTC))
    d = specification(bundle, checked)
    d["cases"][0]["expected_eligible_keys"] = d["cases"][0]["expected_item_keys"] = []
    d["cases"][0]["expected_comparisons"] = {}
    with pytest.raises(AuditError, match="eligibility_conflicts"):
        prepare_cases(ProviderSpec.model_validate(d), checked, datetime.now(UTC))


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:80",
        "http://example.org:80",
        "http://localhost:80",
        "http://u:p@127.0.0.1:80",
        "http://127.0.0.1:80/path",
        "http://127.0.0.1:80/?secret=1",
    ],
)
def test_only_explicit_owned_loopback_origin_is_allowed(url):
    with pytest.raises(AuditError):
        loopback_base_url(url)


def test_cli_existing_output_is_rejected_before_source_reads(bundle, tmp_path, monkeypatch, capsys):
    from pubburi_recommendation import reviewed_provider_acceptance as module

    folder = tmp_path / ".pubburi" / "existing"
    folder.mkdir()
    values = [
        "--" + name + "=" + str(value)
        for name, value in {
            "export-dir": "missing",
            "manifest": "missing",
            "input": "missing",
            "source-receipt": "missing",
            "curation": "missing",
            "business-snapshot": "missing",
            "mapping": "missing",
            "spec": "missing",
            "base-url": "http://127.0.0.1:1",
            "output-dir": folder,
        }.items()
    ]
    monkeypatch.setattr(sys, "argv", ["acceptance", *values])
    assert module.main() == 2
    assert "requires_new_private_output" in capsys.readouterr().err


@pytest.mark.parametrize("mode", ["pass", "bad_response", "changed_file", "expired_end"])
def test_cli_completion_separates_response_failure_and_changed_or_expired_inputs(
    bundle, tmp_path, monkeypatch, mode
):
    from pubburi_recommendation import reviewed_provider_acceptance as module

    checked = load(bundle, now=bundle["now"])
    spec = write(tmp_path / "provider-spec.json", specification(bundle, checked))
    output = tmp_path / ".pubburi" / "acceptance"
    folder, manifest, raw, receipt, curation, snapshot, mapping = bundle["args"]
    values = {
        "export-dir": folder,
        "manifest": manifest,
        "input": raw,
        "source-receipt": receipt,
        "curation": curation,
        "business-snapshot": snapshot,
        "mapping": mapping,
        "family-review": bundle["family_review"],
        "spec": spec,
        "base-url": "http://127.0.0.1:1",
        "output-dir": output,
    }
    argv = ["acceptance"]
    for key, value in values.items():
        argv.extend(["--" + key, str(value)])
    monkeypatch.setattr(sys, "argv", argv)
    calls = []
    original_load = module.load_checked_export
    loads = []

    def load_at_boundary(*args, **kwargs):
        loads.append(True)
        if mode == "expired_end" and len(loads) > 1:
            kwargs["now"] = bundle["now"] + timedelta(seconds=301)
        return original_load(*args, **kwargs)

    monkeypatch.setattr(module, "load_checked_export", load_at_boundary)
    with TestClient(app) as client:

        def local_post(base_url, provider, body):
            result = client.post("/v1/recommendations/" + provider, json=body).json()
            calls.append(provider)
            if mode == "bad_response" and len(calls) == 1:
                result["eligible_count"] = 0
            if mode == "changed_file" and len(calls) == 5:
                path = folder / "b1-demo-request.json"
                path.write_bytes(path.read_bytes() + b" ")
            return result

        monkeypatch.setattr(module, "post_json", local_post)
        code = module.main()
    receipt = json.loads((output / "receipt.json").read_text())
    if mode in ("changed_file", "expired_end"):
        assert code == 2 and receipt["completed"] is False
        assert not (output / "acceptance-report.json").exists()
    else:
        assert code == (0 if mode == "pass" else 1)
        report = json.loads((output / "acceptance-report.json").read_text())
        assert receipt["completed"] is True and report["passed"] == (mode == "pass")
        assert report["passed_contract_cases"] == (5 if mode == "pass" else 4)


def test_checked_loader_and_cli_imports_do_not_restore_or_import_a_model():
    subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; import pubburi_recommendation.checked_export; "
            "import pubburi_recommendation.reviewed_provider_acceptance; "
            "assert not {'numpy','sklearn','pubburi_recommendation.content_model'} "
            "& set(sys.modules)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
