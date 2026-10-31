import copy
import json
import subprocess
import sys
from email.message import Message
from pathlib import Path
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit

import pytest

import pubburi_recommendation.wikidata_collect as module
from pubburi_recommendation.catalog_audit import AuditError, SourceManifest, read_json

ROOT = Path(__file__).resolve().parents[1]


def manifest():
    return SourceManifest.model_validate(read_json(ROOT / "sources/wikidata-structured.json")[0])


def payload():
    return {
        "success": 1,
        "entities": {
            "Q1": {
                "id": "Q1",
                "type": "item",
                "lastrevid": 7,
                "labels": {"en": {"language": "en", "value": "authored contract fixture only"}},
                "claims": {},
            }
        },
    }


def test_live_receipt_binds_raw_projection_and_revision_without_training_approval(
    tmp_path, monkeypatch
):
    content = json.dumps(payload()).encode()
    monkeypatch.setattr(module, "fetch", lambda url: (content, 200))
    output = tmp_path / ".pubburi" / "run"
    receipt = module.collect(manifest(), ["Q1"], output)
    assert receipt["mode"] == "live_get" and receipt["accepted"]
    assert receipt["http_status"] == 200 and receipt["revisions"] == {"Q1": 7}
    assert read_json(output / "entities.json")[1] == receipt["response_sha256"]
    record = json.loads((output / "normalized-records.json").read_text())[0]
    assert record["source_revision"] == 7 and record["source_record_id"] == "Q1"
    assert record["entity_kind"] == "unknown" and record["sku_group"] is None
    assert not receipt["training_ready"] and not receipt["images_fetched"]


@pytest.mark.parametrize(
    "ids",
    [
        [],
        ["Q1"] * 2,
        ["Q0"],
        ["P31"],
        ["Q1&action=edit"],
        ["Q" + "1" * 64],
        [1],
        [f"Q{i}" for i in range(1, 12)],
    ],
)
def test_request_identity_is_bounded_and_never_becomes_arbitrary_api_action(ids):
    with pytest.raises(AuditError):
        module.entity_url(ids)


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("maxlag", "api_maxlag"),
        ("rate", "api_rate_limited"),
        ("unknown_error", "unrecognized_api_error"),
        ("warning", "source_api_warning_requires_review"),
        ("success_missing", "explicit_api_success_required"),
        ("success_bool", "explicit_api_success_required"),
        ("missing_item", "returned_item_ids_must_match_request"),
        ("unexpected_item", "returned_item_ids_must_match_request"),
        ("redirect", "entity_redirect_requires_review"),
        ("entity_redirect", "entity_redirect_requires_review"),
        ("wrong_id", "invalid_entity_identity"),
        ("no_revision", "positive_source_revision_required"),
        ("wrong_claims", "claims_object_required"),
    ],
)
def test_api_errors_or_incomplete_items_cannot_become_empty_success(
    tmp_path, monkeypatch, mutation, reason
):
    body = payload()
    if mutation == "maxlag":
        body = {"error": {"code": "maxlag", "info": "do-not-copy-private-error-info"}}
    if mutation == "rate":
        body = {"error": {"code": "ratelimited"}}
    if mutation == "unknown_error":
        body = {"error": {"code": {"not": "a-code"}, "info": "do-not-copy-private-error-info"}}
    if mutation == "warning":
        body["warnings"] = {"module": "warning"}
    if mutation == "success_missing":
        body.pop("success")
    if mutation == "success_bool":
        body["success"] = True
    if mutation == "missing_item":
        body["entities"] = {}
    if mutation == "unexpected_item":
        body["entities"]["Q2"] = copy.deepcopy(body["entities"]["Q1"])
    if mutation == "redirect":
        body["redirects"] = [{"from": "Q1", "to": "Q2"}]
    if mutation == "entity_redirect":
        body["entities"]["Q1"]["redirect"] = "Q2"
    if mutation == "wrong_id":
        body["entities"]["Q1"]["id"] = "Q2"
    if mutation == "no_revision":
        body["entities"]["Q1"].pop("lastrevid")
    if mutation == "wrong_claims":
        body["entities"]["Q1"]["claims"] = []
    monkeypatch.setattr(module, "fetch", lambda url: (json.dumps(body).encode(), 200))
    output = tmp_path / ".pubburi" / "failed"
    with pytest.raises(AuditError, match=reason):
        module.collect(manifest(), ["Q1"], output)
    receipt = json.loads((output / "receipt.json").read_text())
    assert receipt["accepted"] is False and receipt["http_status"] == 200
    assert receipt["error_code"] == reason
    assert (
        not (output / "entities.json").exists()
        and not (output / "normalized-records.json").exists()
    )
    assert "do-not-copy-private-error-info" not in (output / "receipt.json").read_text()


def test_duplicate_keys_nonfinite_and_oversized_replay_fail_closed(tmp_path, monkeypatch):
    for index, content in enumerate(
        [b'{"success":1,"success":1}', b'{"number":NaN}', b"x" * (module.MAX_INPUT_BYTES + 1)]
    ):
        source = tmp_path / f"input-{index}.json"
        source.write_bytes(content)
        with pytest.raises(AuditError):
            module.collect(manifest(), ["Q1"], tmp_path / ".pubburi" / f"bad-{index}", source)


def test_existing_output_or_unapproved_source_cannot_start_a_request(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "fetch", lambda *args: pytest.fail("must not request"))
    output = tmp_path / ".pubburi" / "old"
    output.mkdir(parents=True)
    (output / "preserved").write_text("keep")
    with pytest.raises(FileExistsError):
        module.collect(manifest(), ["Q1"], output)
    blocked = manifest().model_copy(update={"local_structured_normalization": False})
    with pytest.raises(AuditError, match="reviewed_wikidata_structured_source_required"):
        module.collect(blocked, ["Q1"], tmp_path / ".pubburi" / "blocked")
    assert not (tmp_path / ".pubburi" / "blocked").exists()
    assert (output / "preserved").read_text() == "keep"
    with pytest.raises(AuditError):
        module.collect(manifest(), ["Q1"], tmp_path / "public")


def test_failure_to_commit_success_receipt_leaves_rejected_state(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "fetch", lambda url: (json.dumps(payload()).encode(), 200))
    original = module.write_receipt

    def fail_success(output, receipt):
        if receipt["accepted"]:
            raise OSError("do-not-echo-file-path")
        original(output, receipt)

    monkeypatch.setattr(module, "write_receipt", fail_success)
    output = tmp_path / ".pubburi" / "partial"
    with pytest.raises(OSError):
        module.collect(manifest(), ["Q1"], output)
    receipt = json.loads((output / "receipt.json").read_text())
    assert receipt["accepted"] is False and receipt["error_code"] == "OSError"


class Response:
    status = 200

    def __init__(self, content=b"{}", content_type="application/json"):
        self.content = content
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, maximum):
        assert maximum == module.MAX_INPUT_BYTES + 1
        return self.content[:maximum]


def test_fetch_is_one_identified_get_with_maxlag_and_byte_limit(monkeypatch):
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            assert request.get_method() == "GET" and timeout == 15
            assert request.get_header("User-agent") == module.USER_AGENT
            assert parse_qs(urlsplit(request.full_url).query)["maxlag"] == ["5"]
            return Response(b'{"success":1}')

    monkeypatch.setattr(module, "build_opener", lambda handler: Opener())
    assert module.fetch(module.entity_url(["Q2", "Q1"])) == (b'{"success":1}', 200)
    assert len(calls) == 1
    with pytest.raises(AuditError, match="remote_redirect_not_allowed"):
        module.NoRedirects().redirect_request(None, None, 302, "", {}, "http://localhost/private")


@pytest.mark.parametrize(
    "url",
    [
        "http://www.wikidata.org/w/api.php",
        "https://example.invalid/w/api.php",
        "https://www.wikidata.org/w/api.php?action=edit",
        "https://www.wikidata.org/w/api.php?ids=Q1&maxlag=100",
    ],
)
def test_fetch_cannot_lower_remote_guardrails_or_choose_other_endpoints(monkeypatch, url):
    monkeypatch.setattr(module, "build_opener", lambda *args: pytest.fail("no transport"))
    with pytest.raises(AuditError):
        module.fetch(url)


@pytest.mark.parametrize("failure", ["wrong_type", "too_large", "transport"])
def test_fetch_rejects_non_json_large_and_transport_failures(monkeypatch, failure):
    class Opener:
        def open(self, *args, **kwargs):
            if failure == "transport":
                raise URLError("do-not-copy-network-details")
            return Response(
                b"x" * (module.MAX_INPUT_BYTES + 1) if failure == "too_large" else b"{}",
                "text/html" if failure == "wrong_type" else "application/json",
            )

    monkeypatch.setattr(module, "build_opener", lambda *args: Opener())
    with pytest.raises(AuditError):
        module.fetch(module.entity_url(["Q1"]))


def test_offline_cli_replays_without_claiming_live_acquisition(tmp_path):
    source = tmp_path / "authored.json"
    source.write_text(json.dumps(payload()))
    output = tmp_path / ".pubburi" / "replay"
    command = [
        sys.executable,
        "-m",
        "pubburi_recommendation.wikidata_collect",
        "--manifest",
        str(ROOT / "sources/wikidata-structured.json"),
        "--ids",
        "Q1",
        "--snapshot",
        str(source),
        "--output-dir",
        str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    receipt = json.loads((output / "receipt.json").read_text())
    assert (
        receipt["accepted"]
        and receipt["mode"] == "offline_replay"
        and receipt["http_status"] is None
    )
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 2 and "FileExistsError" in result.stderr


def test_offline_cli_deep_json_has_safe_diagnostic_and_complete_failure_receipt(tmp_path):
    source = tmp_path / "deep-private-source.json"
    source.write_text('{"private-source-marker":' + "[" * 20000 + "0" + "]" * 20000 + "}")
    output = tmp_path / ".pubburi" / "deep-json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pubburi_recommendation.wikidata_collect",
            "--manifest",
            str(ROOT / "sources/wikidata-structured.json"),
            "--ids",
            "Q1",
            "--snapshot",
            str(source),
            "--output-dir",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "json_nesting_exceeds_parser_limit" in result.stderr
    assert "Traceback" not in result.stderr and "private-source-marker" not in result.stderr
    receipt = json.loads((output / "receipt.json").read_text())
    assert (
        receipt["accepted"] is False
        and receipt["error_code"] == "json_nesting_exceeds_parser_limit"
    )
    assert (
        not (output / "entities.json").exists()
        and not (output / "normalized-records.json").exists()
    )
