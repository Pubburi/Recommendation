"""Authored CSV facts test input boundaries without vendoring the actual aT dataset."""

import csv
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from pubburi_recommendation.at_source import (
    HEADERS,
    AtReceipt,
    AtReview,
    normalize_at_csv,
)
from pubburi_recommendation.baseline import Constraints, RecommendationRequest, recommend_baseline
from pubburi_recommendation.catalog_audit import AuditError
from pubburi_recommendation.content_model import ContentProduct, ContentProfile, FittedContentModel

HASH = "a" * 64
EVIDENCE = b"authored provider fact fixture, no real prose"
EVIDENCE_HASH = hashlib.sha256(EVIDENCE).hexdigest()


def raw_csv(rows=None, headers=HEADERS):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(headers)
    if rows is None:
        rows = [
            [
                "가상 원천 A",
                "제외할 창작 소개",
                "0",
                "",
                "",
                "750",
                "",
                "",
                "",
                "",
                "",
                "달다",
                "가상 양조장",
                "주소",
                "",
                "",
            ],
            ["가상 원천 B", "", "10", "", "", "500", "", "", "", "", "", "", "", "", "", ""],
        ]
    writer.writerows(rows)
    return stream.getvalue().encode("cp949")


def receipt(content):
    return AtReceipt(
        schema_version=1,
        evidence_kind="authored_regression_fixture",
        dataset_id="15048755",
        source_version="20260731",
        observed_at_utc="2026-11-05T00:00:00+00:00",
        source_sha256=hashlib.sha256(content).hexdigest(),
        source_bytes=len(content),
        http_status=200,
        normal_public_rate_guard_passed=True,
        images_fetched=False,
    )


def review(content):
    return AtReview.model_validate(
        {
            "schema_version": 1,
            "algorithm": "at-reviewed-source-facts-v1",
            "input_sha256": hashlib.sha256(content).hexdigest(),
            "receipt_sha256": HASH,
            "manifest_sha256": HASH,
            "source_version": "20260731",
            "records": [
                {
                    "row_number": 1,
                    "expected_label": "가상 원천 A",
                    "expected_producer": "가상 양조장",
                    "category": "과실주",
                    "abv_percent": 0.0,
                    "abv_unit": "%",
                    "evidence_url": "https://thesool.com/front/publication/M000000066/view.do?publicationId=fixture",
                    "evidence_sha256": EVIDENCE_HASH,
                    "review_note": "직접 작성한 회귀 사실",
                }
            ],
        }
    )


def run(content, selected=None, **changes):
    args = dict(
        manifest_hash=HASH, receipt_hash=HASH, review=selected, evidence_hashes={EVIDENCE_HASH}
    )
    args.update(changes)
    return normalize_at_csv(content, receipt(content), **args)


def test_curated_fact_zero_is_known_but_other_units_prose_and_business_fields_remain_unknown():
    content = raw_csv()
    report, rows, request = run(content, review(content))
    assert report["records"] == 2 and report["reviewed_rows"] == 1
    assert report["known"] == dict(label=2, producer_name=1, category=1, abv_percent=1, volume_ml=0)
    assert rows[0]["abv_percent"] == 0 and rows[0]["category"] == "과실주"
    assert rows[0]["label"] == "가상 원천 A" and rows[0]["producer_name"] == "가상 양조장"
    assert rows[1]["producer_name"] is None and rows[1]["abv_percent"] is None
    for row in rows:
        assert row["entity_kind"] == "unverified_source_product_record"
        assert row["volume_ml"] is row["taste_tags"] is row["aroma_tags"] is None
        assert row["backend_product_id"] is row["sku_group"] is row["price_krw"] is None
        assert row["availability"] == "unknown" and not row["service_feature_fit_eligible"]
    assert request is None
    serialized = json.dumps(rows, ensure_ascii=False)
    assert (
        "제외할 창작 소개" not in serialized
        and "달다" not in serialized
        and "주소" not in serialized
    )
    assert rows[0]["raw_volume_values"] == ["750", "", ""]


def test_unreviewed_dataset_is_fact_preserving_not_numerical_or_sku_approval():
    report, rows, _ = run(raw_csv())
    assert report["reviewed_rows"] == 0
    assert [row["abv_percent"] for row in rows] == [None, None]
    assert rows[0]["source_record_id"] != rows[1]["source_record_id"]
    assert report["b0_demo_exported"] == report["b1_wire_exports"] == 0


def test_single_container_volume_needs_an_explicit_matching_review():
    content = raw_csv()
    data = review(content).model_dump()
    data["records"][0].update(volume_ml=750, volume_unit="mL", volume_scope="single_container")
    report, rows, request = run(content, AtReview.model_validate(data))
    assert rows[0]["volume_ml"] == 750 and rows[1]["volume_ml"] is None
    assert report["known"]["volume_ml"] == 1
    assert not rows[0]["service_feature_fit_eligible"]
    assert rows[0]["backend_product_id"] is rows[0]["sku_group"] is request is None


@pytest.mark.parametrize(
    "changes",
    [
        {"volume_ml": 750},
        {"volume_unit": "mL", "volume_scope": "single_container"},
        {"volume_ml": 0, "volume_unit": "mL", "volume_scope": "single_container"},
        {"volume_ml": True, "volume_unit": "mL", "volume_scope": "single_container"},
        {"volume_ml": 750, "volume_unit": "L", "volume_scope": "single_container"},
        {"volume_ml": 750, "volume_unit": "mL", "volume_scope": "multipack"},
        {
            "volume_ml": 750,
            "volume_unit": "mL",
            "volume_scope": "single_container",
            "abv_percent": None,
            "abv_unit": None,
        },
    ],
)
def test_volume_without_single_container_unit_or_abv_is_not_a_fact(changes):
    data = review(raw_csv()).model_dump()
    data["records"][0].update(changes)
    with pytest.raises(ValueError):
        AtReview.model_validate(data)


@pytest.mark.parametrize(
    "first,second",
    [("", ""), ("500", ""), ("750x2", ""), ("750", "375"), ("NaN", ""), ("Infinity", "")],
)
def test_volume_review_cannot_override_missing_different_or_multiple_csv_values(first, second):
    source = list(csv.reader(io.StringIO(raw_csv().decode("cp949"))))[1:]
    source[0][5:7] = [first, second]
    content = raw_csv(source)
    data = review(content).model_dump()
    data["records"][0].update(volume_ml=750, volume_unit="mL", volume_scope="single_container")
    with pytest.raises(AuditError, match="volume_requires_matching_single_source_value"):
        run(content, AtReview.model_validate(data))


@pytest.mark.parametrize(
    "field,value",
    [
        ("input_sha256", "b" * 64),
        ("receipt_sha256", "b" * 64),
        ("manifest_sha256", "b" * 64),
        ("source_version", "20260101"),
    ],
)
def test_curation_cannot_cross_source_receipt_manifest_or_version(field, value):
    content = raw_csv()
    data = review(content).model_dump()
    data[field] = value
    with pytest.raises(AuditError, match="snapshot_hash_or_version_mismatch"):
        run(content, AtReview.model_validate(data))


@pytest.mark.parametrize(
    "field,value",
    [
        ("expected_label", "다른 이름"),
        ("expected_producer", None),
        ("row_number", 3),
        ("abv_percent", 1.0),
        ("evidence_sha256", "b" * 64),
    ],
)
def test_selected_rows_require_exact_fields_single_quantity_and_evidence(field, value):
    content = raw_csv()
    data = review(content).model_dump()
    data["records"][0][field] = value
    with pytest.raises(AuditError):
        run(content, AtReview.model_validate(data))


def test_duplicate_identity_and_multiple_abv_are_not_deduplicated_or_selected_by_position():
    source = list(csv.reader(io.StringIO(raw_csv().decode("cp949"))))[1:]
    duplicate = raw_csv([source[0], source[0]])
    report, rows, _ = run(duplicate)
    assert report["duplicate_whole_rows"] == 1 and report["ambiguous_identity_rows"] == 2
    assert all(row["duplicate_identity"] for row in rows)
    with pytest.raises(AuditError, match="duplicate_identity"):
        run(duplicate, review(duplicate))
    source[0][3] = "5"
    multiple = raw_csv(source)
    assert run(multiple)[0]["multiple_abv_rows"] == 1
    with pytest.raises(AuditError, match="matching_single_source_value"):
        run(multiple, review(multiple))


@pytest.mark.parametrize(
    "content", [b"\xff", raw_csv(headers=tuple(reversed(HEADERS))), raw_csv([["short"]])]
)
def test_bad_encoding_header_and_width_fail_without_source_content(content):
    with pytest.raises(AuditError):
        run(content)


def test_receipt_bytes_and_length_are_both_bound():
    content = raw_csv()
    captured = receipt(content)
    for change in ({"source_sha256": "b" * 64}, {"source_bytes": len(content) + 1}):
        with pytest.raises(AuditError, match="source_bytes_mismatch"):
            normalize_at_csv(
                content, captured.model_copy(update=change), manifest_hash=HASH, receipt_hash=HASH
            )


def test_curated_source_facts_feed_existing_model_only_with_explicit_offline_ids():
    content = raw_csv()
    _, rows, _ = run(content, review(content))
    # Explicit authored evaluation availability/local IDs are not facts read from aT.
    products = [
        ContentProduct(
            product_id=row["source_row_number"],
            sku_group=f"offline-row-{i}",
            available=True,
            category=row["category"],
            abv_percent=row["abv_percent"],
        )
        for i, row in enumerate(rows)
    ]
    model = FittedContentModel.fit(products)
    assert model.summary["numeric_fit"]["abv_percent"]["observed_count"] == 1
    assert not model.summary["numeric_fit"]["abv_percent"]["active"]
    cold = model.rank(products, ContentProfile())
    assert [row.product_id for row in cold.items] == [1, 2]
    assert cold.fallback_reason == "no_supported_preferences"
    hard = Constraints(max_abv_percent=0)
    assert [row.product_id for row in model.rank(products, ContentProfile(), hard).items] == [1]
    b0 = RecommendationRequest(
        catalog=[
            {
                k: v
                for k, v in row.model_dump().items()
                if k in ("product_id", "available", "category", "price_krw", "abv_percent")
            }
            for row in products
        ],
        constraints=hard,
    )
    assert [row.product_id for row in recommend_baseline(b0).items] == [1]


def test_existing_audit_cli_curates_csv_and_preserves_existing_outputs(tmp_path):
    root = Path(__file__).resolve().parents[1]
    manifest = root / "sources/at-traditional-liquor.json"
    content = raw_csv()
    source = tmp_path / "source.csv"
    source.write_bytes(content)
    captured = tmp_path / "receipt.json"
    captured.write_text(receipt(content).model_dump_json())
    data = review(content).model_dump()
    data.update(
        manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
        receipt_sha256=hashlib.sha256(captured.read_bytes()).hexdigest(),
    )
    selected = tmp_path / "review.json"
    selected.write_text(json.dumps(data))
    evidence = tmp_path / "evidence.html"
    evidence.write_bytes(EVIDENCE)
    output = tmp_path / ".pubburi/output"
    command = [
        sys.executable,
        "-m",
        "pubburi_recommendation.catalog_audit",
        "--manifest",
        str(manifest),
        "--input",
        str(source),
        "--receipt",
        str(captured),
        "--review",
        str(selected),
        "--fact-evidence",
        str(evidence),
        "--output-dir",
        str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    rows = json.loads((output / "normalized-records.json").read_text())
    assert rows[0]["abv_percent"] == 0 and not (output / "b0-demo-request.json").exists()
    previous = (output / "normalized-records.json").read_bytes()
    assert subprocess.run(command, capture_output=True, check=False).returncode == 2
    assert (output / "normalized-records.json").read_bytes() == previous


def test_source_only_curation_cannot_enter_existing_business_export_authority(tmp_path):
    from pubburi_recommendation.catalog_authority import load_export_catalog

    root = Path(__file__).resolve().parents[1]
    selected = tmp_path / "review.json"
    selected.write_text(review(raw_csv()).model_dump_json())
    with pytest.raises(AuditError, match="source_catalog_normalization_not_approved"):
        load_export_catalog(
            root / "sources/at-traditional-liquor.json",
            tmp_path / "unopened-private-source.csv",
            tmp_path / "unopened-private-receipt.json",
            selected,
        )


def test_cli_missing_receipt_diagnostic_is_fixed_and_contains_no_private_input(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pubburi_recommendation.catalog_audit",
            "--manifest",
            "sources/at-traditional-liquor.json",
            "--input",
            str(tmp_path / "private-label.csv"),
            "--output-dir",
            str(tmp_path / ".pubburi/out"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert result.stderr == "Catalog audit failed: at_public_download_receipt_required\n"
    assert not (tmp_path / ".pubburi/out").exists()
