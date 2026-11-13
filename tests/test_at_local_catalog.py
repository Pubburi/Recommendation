"""Authored facts exercise the local authority without inventing public-source evidence."""

import copy
import csv
import hashlib
import io
import json
from argparse import Namespace
from pathlib import Path

import pytest
from pydantic import ValidationError

from pubburi_recommendation import at_local_catalog as compiler
from pubburi_recommendation.at_source import HEADERS
from pubburi_recommendation.catalog_audit import AuditError


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def inputs(tmp_path):
    manifest = json.loads(
        (Path(__file__).resolve().parents[1] / "sources/at-traditional-liquor.json").read_text()
    )
    manifest_path = write(tmp_path / "manifest.json", manifest)
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(HEADERS)
    writer.writerow(
        [
            "가상 약주",
            "보존 금지 소개",
            "0",
            "",
            "",
            "300",
            "",
            "",
            "",
            "",
            "",
            "",
            "가상 양조장",
            "",
            "",
            "",
        ]
    )
    writer.writerow(
        ["미선택 원천", "", "10", "", "", "700", "", "", "", "", "", "", "다른 양조장", "", "", ""]
    )
    raw = tmp_path / "raw.csv"
    raw.write_bytes(stream.getvalue().encode("cp949"))
    evidence = tmp_path / "evidence.html"
    evidence.write_bytes(b"Authored zero-percent single 300mL yakju, no public provenance")
    receipt = write(
        tmp_path / "receipt.json",
        {
            "schema_version": 1,
            "evidence_kind": "authored_regression_fixture",
            "dataset_id": "15048755",
            "source_version": "20260731",
            "observed_at_utc": "2026-11-05T00:00:00Z",
            "source_sha256": sha(raw),
            "source_bytes": raw.stat().st_size,
            "http_status": 200,
            "normal_public_rate_guard_passed": True,
            "images_fetched": False,
        },
    )
    review = write(
        tmp_path / "review.json",
        {
            "schema_version": 1,
            "algorithm": "at-reviewed-source-facts-v1",
            "input_sha256": sha(raw),
            "receipt_sha256": sha(receipt),
            "manifest_sha256": sha(manifest_path),
            "source_version": "20260731",
            "records": [
                {
                    "row_number": 1,
                    "expected_label": "가상 약주",
                    "expected_producer": "가상 양조장",
                    "category": "약주",
                    "abv_percent": 0.0,
                    "abv_unit": "%",
                    "volume_ml": 300,
                    "volume_unit": "mL",
                    "volume_scope": "single_container",
                    "evidence_url": "https://thesool.com/front/publication/M000000066/view.do?publicationId=fixture",
                    "evidence_sha256": sha(evidence),
                    "review_note": "Authored fixture only",
                }
            ],
        },
    )
    selection = write(
        tmp_path / "selection.json",
        {
            "schema_version": 1,
            "algorithm": "at-local-catalog-selection-v1",
            "catalog_version": "fixture-v1",
            "reviewed_at_utc": "2026-11-06T00:00:00Z",
            "input_sha256": sha(raw),
            "receipt_sha256": sha(receipt),
            "manifest_sha256": sha(manifest_path),
            "review_sha256": sha(review),
            "records": [
                {
                    "catalog_record_id": "explicit-row-a",
                    "source_row_number": 1,
                    "source_variant_group": "explicit-source-family",
                }
            ],
        },
    )
    return Namespace(
        manifest=manifest_path,
        input=raw,
        receipt=receipt,
        review=review,
        selection=selection,
        fact_evidence=[evidence],
        output_dir=tmp_path / ".pubburi" / "out",
    )


def compile(args):
    return compiler.compile_catalog(
        args.manifest, args.input, args.receipt, args.review, args.selection, args.fact_evidence
    )


def revise(args, field, update):
    path = getattr(args, field)
    value = json.loads(path.read_text())
    update(value)
    write(path, value)
    # Rebind intentional manual-review edits so downstream semantic gates are exercised.
    if field in ("manifest", "receipt", "review"):
        review = json.loads(args.review.read_text())
        if field != "review":
            review[field + "_sha256"] = sha(path)
            write(args.review, review)
        selection = json.loads(args.selection.read_text())
        selection.update(
            manifest_sha256=sha(args.manifest),
            receipt_sha256=sha(args.receipt),
            review_sha256=sha(args.review),
        )
        write(args.selection, selection)


def test_exact_source_facts_zero_capture_unknown_and_explicit_local_scope(inputs):
    result = compile(inputs).model_dump(mode="json")
    assert result["scope"] == "REVIEWED_LOCAL_CATALOG"
    assert result["source"]["evidence_kind"] == "authored_regression_fixture"
    assert result["source"]["captured_at_utc"] == "2026-11-05T00:00:00Z"
    assert result["reviewed_at_utc"] == "2026-11-06T00:00:00Z"
    assert len(result["records"]) == 1
    row = result["records"][0]
    assert row["catalog_record_id"] == "explicit-row-a"
    assert row["facts"] == {
        "label": "가상 약주",
        "producer_name": "가상 양조장",
        "source_category": "약주",
        "category": "약 · 청주",
        "abv_percent": 0.0,
        "volume_ml": 300,
        "gtin": None,
        "taste_tags": None,
        "aroma_tags": None,
        "image_url": None,
        "description": None,
    }
    encoded = json.dumps(result, ensure_ascii=False)
    assert all(
        value not in encoded
        for value in (
            "보존 금지 소개",
            "미선택 원천",
            "backend_product_id",
            "available",
            "price",
            "valid_until",
        )
    )
    assert result["source"]["input_sha256"] == sha(inputs.input)
    assert result["source"]["selection_sha256"] == sha(inputs.selection)


@pytest.mark.parametrize("field", ["input", "receipt", "review", "manifest", "evidence"])
def test_changed_original_authority_is_rejected(inputs, field):
    path = inputs.fact_evidence[0] if field == "evidence" else getattr(inputs, field)
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(AuditError):
        compile(inputs)


@pytest.mark.parametrize(
    "notice",
    [
        '<div class="opencode nuri4"><img src="/images/front/cont/opencode4.png"></div>',
        "<span>공공누리 제4유형</span>",
        '<div class="opencode nuri3">공공누리 제3유형</div>',
        "<p>출처표시 + 상업적 이용금지 + 변경&nbsp;<strong>금지</strong></p>",
        "<p>KOGL Type 4</p>",
        '<footer id="footer"><p>본 저작물 변경 금지</p></footer>',
        '<footer id="footer"><a href="https://www.kogl.or.kr/info/license.do">'
        '<img src="/images/front/cont/opencode4.png" alt="공공누리 제4유형"></a></footer>',
        '<footer id="footer"><a href="/copyright">본 자료는 변경 금지입니다</a></footer>',
        '<footer id="footer"><a href="https://www.kogl.or.kr/info/license.do" '
        'rel="license">공공누리 제4유형 안내</a></footer>',
    ],
)
def test_local_authority_holds_a_referenced_publication_with_restrictive_terms(inputs, notice):
    evidence = inputs.fact_evidence[0]
    evidence.write_text(notice, encoding="utf-8")
    revise(inputs, "review", lambda x: x["records"][0].update(evidence_sha256=sha(evidence)))

    with pytest.raises(AuditError, match="at_local_catalog_publication_restricts_derivatives"):
        compile(inputs)


def test_local_authority_ignores_terms_in_an_unreferenced_capture(inputs, tmp_path):
    unused = tmp_path / "unreferenced.html"
    unused.write_text("<span>공공누리 제4유형</span>", encoding="utf-8")
    inputs.fact_evidence.append(unused)

    assert len(compile(inputs).records) == 1


def test_local_authority_distinguishes_site_footer_navigation_from_publication_terms(inputs):
    evidence = inputs.fact_evidence[0]
    evidence.write_text(
        '<article>검수한 상품 정보</article><footer id="footer">\n'
        '<a href="https://www.kogl.or.kr/info/license.do">공공누리 제4유형 안내</a>\n</footer>',
        encoding="utf-8",
    )
    revise(inputs, "review", lambda x: x["records"][0].update(evidence_sha256=sha(evidence)))

    assert len(compile(inputs).records) == 1


@pytest.mark.parametrize(
    "change",
    [
        lambda x: x["additional_conditions"].remove(compiler.LOCAL_POLICY),
        lambda x: x.update(structured_feature_fit=False),
        lambda x: x.update(source_url="https://example.org/unreviewed"),
        lambda x: x.update(provider="unreviewed provider"),
    ],
)
def test_old_or_wrong_project_scope_is_not_approval(inputs, change):
    revise(inputs, "manifest", change)
    with pytest.raises(AuditError, match="scope_not_reviewed"):
        compile(inputs)


@pytest.mark.parametrize(
    "change",
    [
        lambda x: x["records"][0].update(volume_ml=None, volume_unit=None, volume_scope=None),
        lambda x: x["records"][0].update(volume_ml=700),
        lambda x: x["records"][0].update(abv_percent=1.0),
        lambda x: x["records"][0].update(expected_producer="다른 양조장"),
        lambda x: x["records"][0].update(category="unknown category"),
    ],
)
def test_missing_or_conflicting_facts_cannot_be_promoted(inputs, change):
    revise(inputs, "review", change)
    with pytest.raises(AuditError):
        compile(inputs)


@pytest.mark.parametrize(
    "change",
    [
        lambda x: x["records"].append(copy.deepcopy(x["records"][0])),
        lambda x: x["records"][0].update(source_row_number=2),
        lambda x: x["records"][0].update(source_row_number=True),
        lambda x: x["records"][0].update(backend_product_id=5),
        lambda x: x.update(reviewed_at_utc="2026-11-04T00:00:00Z"),
        lambda x: x.update(reviewed_at_utc="2026-11-06T00:00:00"),
        lambda x: x.update(schema_version=True),
    ],
)
def test_selection_requires_exact_unique_explicit_rows_and_utc(inputs, change):
    revise(inputs, "selection", change)
    with pytest.raises((AuditError, ValidationError)):
        compile(inputs)


@pytest.mark.parametrize(
    "change",
    [
        lambda x: x.update(available=True),
        lambda x: x.update(valid_until_utc="2027-01-01T00:00:00Z"),
        lambda x: x["records"][0]["facts"].update(gtin="1234567890123"),
        lambda x: x["records"][0]["facts"].update(taste_tags=[]),
        lambda x: x["records"][0]["facts"].update(volume_ml=True),
        lambda x: x["records"][0]["facts"].update(category="과실주"),
        lambda x: x["records"][0].update(source_record_id="Q123"),
        lambda x: x["source"].update(evidence_kind="reviewed_public_source"),
        lambda x: x.update(schema_version=True),
        lambda x: x["license"].update(raw_redistribution=0),
        lambda x: x["records"][0]["evidence"].update(url="https://example.org/unreviewed"),
    ],
)
def test_typed_authority_rejects_wrong_scope_fabricated_identity_and_known_unknown(inputs, change):
    data = compile(inputs).model_dump(mode="json")
    change(data)
    with pytest.raises(ValidationError):
        compiler.AtLocalCatalog.model_validate(data)


def test_publication_pins_bytes_and_never_overwrites_or_blesses_a_race(inputs, monkeypatch):
    actual = compiler.compile_catalog
    calls = 0

    def changed(*args):
        nonlocal calls
        calls += 1
        result = actual(*args)
        if calls == 2:
            result.records[0].facts.volume_ml = 700
        return result

    monkeypatch.setattr(compiler, "compile_catalog", changed)
    with pytest.raises(AuditError, match="inputs_changed"):
        compiler.publish_catalog(inputs)
    assert not (inputs.output_dir / "catalog-authority.json").exists()
    assert json.loads((inputs.output_dir / "receipt.json").read_text())["completed"] is False
    monkeypatch.setattr(compiler, "compile_catalog", actual)
    with pytest.raises(AuditError, match="new_private_output"):
        compiler.publish_catalog(inputs)
    inputs.output_dir = inputs.output_dir.parent / "success"
    receipt = compiler.publish_catalog(inputs)
    assert receipt["completed"] and receipt["authority_sha256"] == sha(
        inputs.output_dir / "catalog-authority.json"
    )
    assert not (inputs.output_dir / "catalog-authority.json.pending").exists()
    assert (inputs.output_dir / "catalog-authority.json").stat().st_mode & 0o077 == 0


def test_future_review_and_public_output_do_not_publish(inputs):
    revise(inputs, "selection", lambda x: x.update(reviewed_at_utc="2099-01-01T00:00:00Z"))
    with pytest.raises(AuditError, match="in_future"):
        compiler.publish_catalog(inputs)
    assert not inputs.output_dir.exists()
    inputs.output_dir = inputs.output_dir.parent.parent / "public-output"
    with pytest.raises(AuditError, match="new_private_output"):
        compiler.publish_catalog(inputs)
