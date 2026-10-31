"""One bounded Wikidata GET or offline replay; API errors never become empty catalogs."""

import argparse
import datetime
import hashlib
import json
import sys
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pubburi_recommendation.catalog_audit import (
    MAX_INPUT_BYTES,
    QID,
    AuditError,
    SourceManifest,
    normalize_entities,
    parse_json_bytes,
    read_json,
)

ENDPOINT = "https://www.wikidata.org/w/api.php"
USER_AGENT = "PubburiCatalogAudit/0.1 (https://github.com/Pubburi/Recommendation)"
MAX_ENTITIES = 10
API_ERRORS = {
    "maxlag": "api_maxlag",
    "ratelimited": "api_rate_limited",
    "readonly": "api_read_only",
    "badvalue": "api_bad_value",
}


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        raise AuditError("remote_redirect_not_allowed")


def entity_url(ids: list[str]) -> str:
    if (
        not ids
        or len(ids) > MAX_ENTITIES
        or any(not isinstance(qid, str) or len(qid) > 32 or not QID.fullmatch(qid) for qid in ids)
    ):
        raise AuditError("request_requires_1_to_10_item_ids")
    if len(set(ids)) != len(ids):
        raise AuditError("request_item_ids_must_be_unique")
    return (
        ENDPOINT
        + "?"
        + urlencode(
            {
                "action": "wbgetentities",
                "ids": "|".join(sorted(ids)),
                "props": "info|labels|claims",
                "languages": "ko|en",
                "format": "json",
                "maxlag": 5,
            }
        )
    )


def declared_body_length(headers) -> int | None:
    lengths = headers.get_all("Content-Length", [])
    encodings = headers.get_all("Transfer-Encoding", [])
    # Conservative for ambiguous framing; HTTPResponse otherwise chooses a length silently.
    if len(lengths) > 1 or len(encodings) > 1:
        raise AuditError("remote_protocol_failed")
    if encodings and (lengths or encodings[0].strip(" \t").lower() != "chunked"):
        raise AuditError("remote_protocol_failed")
    if not lengths:
        return None  # Chunked completion is checked by HTTPResponse; no-length bodies end at EOF.
    token = lengths[0].strip(" \t")
    if not token or len(token) > 20 or not token.isascii() or not token.isdecimal():
        raise AuditError("remote_protocol_failed")
    expected = int(token)
    if expected > MAX_INPUT_BYTES:
        raise AuditError("input_exceeds_10_mib")
    return expected


def fetch(url: str) -> tuple[bytes, int]:
    parsed = urlsplit(url)
    parameters = parse_qs(parsed.query)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.wikidata.org"
        or parsed.path != "/w/api.php"
        or parsed.fragment
        or len(parameters.get("ids", [])) != 1
        or url != entity_url(parameters["ids"][0].split("|"))
    ):
        raise AuditError("fixed_wikidata_request_required")
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with build_opener(NoRedirects()).open(request, timeout=15) as response:
            if response.status != 200:
                raise AuditError("unexpected_http_status")
            if response.headers.get_content_type() != "application/json":
                raise AuditError("unexpected_response_content_type")
            expected_length = declared_body_length(response.headers)
            if response.headers.get_all("Transfer-Encoding", []) and not getattr(
                response, "chunked", False
            ):
                raise AuditError("remote_protocol_failed")
            content = response.read(MAX_INPUT_BYTES + 1)
            if len(content) > MAX_INPUT_BYTES:
                raise AuditError("input_exceeds_10_mib")
            if expected_length is not None and len(content) != expected_length:
                raise AuditError("remote_protocol_failed")
            return content, response.status
    except HTTPException as error:
        raise AuditError("remote_protocol_failed") from error
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise AuditError("remote_transport_failed") from error


def check_payload(payload: dict, ids: list[str]) -> list[dict]:
    if "error" in payload:
        error = payload["error"]
        code = error.get("code") if isinstance(error, dict) else None
        raise AuditError(
            API_ERRORS.get(code, "unrecognized_api_error")
            if isinstance(code, str)
            else "unrecognized_api_error"
        )
    if payload.get("warnings"):
        raise AuditError("source_api_warning_requires_review")
    if payload.get("redirects"):
        raise AuditError("entity_redirect_requires_review")
    if type(payload.get("success")) is not int or payload["success"] != 1:
        raise AuditError("explicit_api_success_required")
    entities = payload.get("entities")
    if not isinstance(entities, dict) or set(entities) != set(ids):
        raise AuditError("returned_item_ids_must_match_request")
    if any(isinstance(entity, dict) and "redirect" in entity for entity in entities.values()):
        raise AuditError("entity_redirect_requires_review")
    # Checks exact item IDs, positive revisions, label shape and supported quantity/claim shape.
    return normalize_entities(payload)


def write_receipt(output: Path, receipt: dict) -> None:
    temporary = output / "receipt.tmp"
    temporary.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output / "receipt.json")


def collect(
    manifest: SourceManifest, ids: list[str], output: Path, snapshot: Path | None = None
) -> dict:
    if (
        manifest.source_id != "wikidata-structured"
        or manifest.license_label != "CC0-1.0"
        or not manifest.local_structured_normalization
    ):
        raise AuditError("reviewed_wikidata_structured_source_required")
    url = entity_url(ids)
    if ".pubburi" not in output.resolve().parts:
        raise AuditError("outputs_must_be_inside_private_pubburi_directory")
    # Reserve once before reading the input or making a request; never overwrite an old snapshot.
    output.mkdir(parents=True, exist_ok=False)
    receipt = {
        "schema_version": 1,
        "mode": "live_get" if snapshot is None else "offline_replay",
        "request_url": url,
        "requested_ids": sorted(ids),
        "observed_at_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "accepted": False,
        "http_status": None,
        "response_bytes": None,
        "response_sha256": None,
        "error_code": None,
        "structured_data_license": "CC0-1.0",
        "license_evidence": "https://www.wikidata.org/wiki/Wikidata:Licensing",
        "manifest_sha256": hashlib.sha256(manifest.model_dump_json().encode()).hexdigest(),
        "images_fetched": False,
        "identity_review": "not_performed",
        "training_ready": False,
    }
    write_receipt(output, receipt)
    try:
        if snapshot is None:
            content, receipt["http_status"] = fetch(url)
        else:
            with snapshot.open("rb") as source:
                content = source.read(MAX_INPUT_BYTES + 1)
        receipt["response_bytes"] = len(content)
        payload, receipt["response_sha256"] = parse_json_bytes(content)
        records = check_payload(payload, ids)
        (output / "entities.json").write_bytes(content)
        (output / "normalized-records.json").write_text(
            json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        receipt.update(
            accepted=True,
            entities=len(records),
            revisions={record["source_record_id"]: record["source_revision"] for record in records},
        )
        write_receipt(output, receipt)
        return receipt
    except (OSError, ValueError, TypeError, KeyError) as error:
        receipt["accepted"] = False
        receipt["error_code"] = (
            str(error) if isinstance(error, AuditError) else type(error).__name__
        )
        write_receipt(output, receipt)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--ids", nargs="+", required=True)
    parser.add_argument(
        "--snapshot", type=Path, help="Replay a local payload without any HTTP request"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = SourceManifest.model_validate(read_json(args.manifest)[0])
        receipt = collect(manifest, args.ids, args.output_dir, args.snapshot)
        print(json.dumps({key: receipt[key] for key in ("mode", "accepted", "entities")}))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        reason = str(error) if isinstance(error, AuditError) else type(error).__name__
        print(f"Wikidata collection failed: {reason}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
