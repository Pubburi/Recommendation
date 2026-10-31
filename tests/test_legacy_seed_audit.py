import json
import subprocess
import sys
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from pubburi_recommendation.catalog_audit import AuditError
from pubburi_recommendation.legacy_seed_audit import (
    LegacyManifest,
    audit_seed,
    file_inventory,
    mapped_asset_name,
)
from pubburi_recommendation.seed_sql import extract_products

ROOT = Path(__file__).resolve().parents[1]
HEADER = "INSERT INTO t_product (name, type, price, img, abv, order_count) VALUES "
ROW = "('fixture bottle 500ml 5%', 'fixture-kind', 1000, 'one.png', 5.0, 99)"


def make_assets(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "one.webp").write_bytes(b"RIFF\x08\x00\x00\x00WEBPfictional-sample")
    return assets


def test_only_active_products_are_extracted_without_user_or_commented_rows():
    sql = (
        "INSERT INTO t_user VALUES ('private-user@example.invalid', 'not-a-real-password');\n"
        "-- " + HEADER + ROW + ";\n"
        "# " + HEADER + ROW + ";\n"
        "/* " + HEADER + ROW + "; */\n" + HEADER + ROW + ";"
    )
    products, count = extract_products(sql)
    assert count == len(products) == 1
    assert products[0]["price"] == Decimal(1000)
    assert "private-user" not in str(products) and "not-a-real-password" not in str(products)


def test_quotes_comments_semicolons_and_column_order_are_literal_data():
    rows, _ = extract_products(
        "INSERT INTO `t_product` (`img`,name,type,price,abv,order_count) VALUES "
        "('one.png','it''s; -- not /* a comment */', 'x#y',0,0.0,0);"
    )
    assert rows[0]["name"] == "it's; -- not /* a comment */"
    assert rows[0]["type"] == "x#y" and rows[0]["price"] == 0


@pytest.mark.parametrize(
    "sql",
    [
        HEADER + "('x','y',1,'a.png',NOW(),0);",
        HEADER + "('x','y',1,'a.png',1e2,0);",
        HEADER + "('x','y',1,'a.png',NaN,0);",
        HEADER + "('x','y',1,'a.png',2,0) ON DUPLICATE KEY UPDATE price=1;",
        HEADER + "('back\\slash','y',1,'a.png',2,0);",
        HEADER + "(\"double quote\",'y',1,'a.png',2,0);",
        HEADER + "('x','y',1,'a.png',2);",
        HEADER + ROW + ",;",
        HEADER + ROW,
        "INSERT IGNORE INTO t_product (name,type,price,img,abv,order_count) VALUES " + ROW + ";",
        "INSERT INTO db.t_product (name,type,price,img,abv,order_count) VALUES " + ROW + ";",
        "INSERT INTO t_product SELECT * FROM hidden;",
        "INSERT INTO t_product (name,type,price,img,abv,abv) VALUES " + ROW + ";",
        "INSERT INTO t_product (na`me,type,price,img,abv,order_count) VALUES " + ROW + ";",
        "/*! " + HEADER + ROW + "; */",
        "/* nested /* unsupported */ */" + HEADER + ROW + ";",
        "/* incomplete",
        HEADER + "('incomplete);",
    ],
)
def test_unsupported_syntax_is_rejected_without_execution_or_raw_diagnostics(sql):
    with pytest.raises(AuditError) as raised:
        extract_products(sql)
    assert "incomplete" not in str(raised.value)
    assert "hidden" not in str(raised.value)


@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE t_product SET price=5;",
        "REPLACE INTO t_product VALUES (1);",
        "DELETE FROM t_product;",
        "TRUNCATE TABLE t_product;",
        "ALTER TABLE T_PRODUCT DROP abv;",
        "DELETE p FROM t_product AS p WHERE p.id=1;",
        "REPLACE LOW_PRIORITY INTO t_product VALUES (1);",
        "WITH c AS (SELECT 1) UPDATE t_product SET price=5;",
        "LOAD DATA INFILE 'fictional.csv' INTO TABLE t_product;",
        "RENAME TABLE t_product TO t_product_archived;",
        "RENAME TABLE archived_product TO t_product;",
    ],
)
def test_non_insert_product_mutations_cannot_silently_change_the_audited_snapshot(mutation):
    with pytest.raises(AuditError, match="non_insert_product_mutation_not_supported"):
        extract_products(HEADER + ROW + ";" + mutation)


@pytest.mark.parametrize(
    "unrelated",
    [
        "UPDATE t_user SET name='t_product';",
        "WITH c AS (SELECT 1) UPDATE t_user SET name='t_product';",
        "LOAD DATA INFILE 't_product.csv' INTO TABLE t_user;",
        "WITH c AS (SELECT * FROM t_product) SELECT * FROM c;",
        "RENAME TABLE unrelated TO unrelated_archive;",
    ],
)
def test_unrelated_tables_and_literal_product_mentions_are_not_mutations(unrelated):
    products, inserts = extract_products(HEADER + ROW + ";" + unrelated)
    assert len(products) == inserts == 1


def test_oversized_product_catalog_is_bounded():
    with pytest.raises(AuditError, match="seed_exceeds_2000_products"):
        extract_products(HEADER + ",".join([ROW] * 2001) + ";")


def test_audit_preserves_demo_values_but_never_infers_verified_features_or_ids(tmp_path):
    inventory, inventory_hash = file_inventory(make_assets(tmp_path))
    report, records = audit_seed(HEADER + ROW + ";", "a" * 64, inventory, inventory_hash)
    record = records[0]
    assert record["seed_row_ordinal"] == 1 and record["backend_product_id"] is None
    assert record["demo_price_krw"] == 1000 and record["demo_order_count"] == 99
    assert record["unverified_abv_percent"] == 5
    assert all(
        record[field] is None
        for field in (
            "verified_volume_ml",
            "verified_abv_percent",
            "verified_category",
            "verified_sku_group",
            "actual_price_krw",
            "observed_popularity",
            "taste_tags",
            "aroma_tags",
        )
    )
    assert not record["feature_fit_eligible"] and report["feature_fit_eligible_rows"] == 0
    assert report["mapped_images_readable"] == 1
    assert report["source_reference_files_readable"] == 0  # Converted WebP is the actual web path.
    assert report["row_issue_counts"] == {}


def test_unknown_and_real_zero_or_invalid_values_are_distinguished(tmp_path):
    inventory, inventory_hash = file_inventory(make_assets(tmp_path))
    sql = HEADER + "('zero','kind',0,'one.png',0,0),(NULL,'',-1,'one.png',101,0.5);"
    report, records = audit_seed(sql, "b" * 64, inventory, inventory_hash)
    assert records[0]["demo_price_krw"] == records[0]["unverified_abv_percent"] == 0
    assert records[1]["name"] is records[1]["category"] is records[1]["demo_price_krw"] is None
    assert len(records[1]["issues"]) == 5
    assert report["row_issue_counts"]["missing_or_invalid:unverified_abv_percent"] == 1


def test_duplicates_reconcile_rows_names_and_shared_assets_without_claiming_skus(tmp_path):
    inventory, inventory_hash = file_inventory(make_assets(tmp_path))
    sql = (
        HEADER
        + ROW
        + ","
        + ROW
        + ",(' FIXTURE BOTTLE 500ml 5% ','fixture-kind',2000,'one.jpg',5,1);"
    )
    report, _ = audit_seed(sql, "c" * 64, inventory, inventory_hash)
    assert report["exact_duplicate_rows"] == {
        "duplicate_groups": 1,
        "affected_rows": 2,
        "extra_rows": 1,
    }
    assert report["normalized_name_duplicates"] == {
        "duplicate_groups": 1,
        "affected_rows": 3,
        "extra_rows": 2,
    }
    assert report["shared_mapped_asset_references"]["affected_rows"] == 3
    assert report["feature_fit_eligible_rows"] == 0


def test_decimal_equivalence_and_quoted_number_types_are_not_confused(tmp_path):
    inventory, inventory_hash = file_inventory(make_assets(tmp_path))
    sql = (
        HEADER
        + ROW
        + ","
        + ROW.replace("1000", "1000.00")
        + ","
        + ROW.replace("1000", "'1000'")
        + ";"
    )
    report, rows = audit_seed(sql, "e" * 64, inventory, inventory_hash)
    assert report["exact_duplicate_rows"]["affected_rows"] == 2
    assert rows[0]["seed_row_fingerprint"] == rows[1]["seed_row_fingerprint"]
    assert rows[2]["seed_row_fingerprint"] != rows[0]["seed_row_fingerprint"]
    assert rows[2]["demo_price_krw"] is None


def test_nonzero_decimal_underflow_cannot_become_observed_zero(tmp_path):
    inventory, inventory_hash = file_inventory(make_assets(tmp_path))
    tiny = "0." + "0" * 400 + "1"
    _, rows = audit_seed(
        HEADER + ROW.replace("5.0", tiny) + ";", "f" * 64, inventory, inventory_hash
    )
    assert rows[0]["unverified_abv_percent"] is None
    assert "missing_or_invalid:unverified_abv_percent" in rows[0]["issues"]


def test_exact_decimal_fingerprints_do_not_round_through_global_precision(tmp_path):
    inventory, inventory_hash = file_inventory(make_assets(tmp_path))
    sql = (
        HEADER
        + ROW.replace("5.0", "5.00000000000000000000000000001")
        + ","
        + ROW.replace("5.0", "5.00000000000000000000000000002")
        + ";"
    )
    with localcontext() as context:
        context.prec = 5
        report, rows = audit_seed(sql, "e" * 64, inventory, inventory_hash)
    assert report["exact_duplicate_rows"]["affected_rows"] == 0
    assert rows[0]["seed_row_fingerprint"] != rows[1]["seed_row_fingerprint"]


@pytest.mark.parametrize(
    "reference,expected",
    [
        ("one.PNG", "one.webp"),
        ("one.JPEG", "one.webp"),
        ("one.webp", "one.webp"),
        ("/images/pub/one.png", "one.webp"),
        ("../one.png", None),
        ("/images/category/one.png", None),
        ("https://example.invalid/one.png", None),
        ("one%2f.png", None),
        ("one.png?token=demo", None),
        ("one.webp#fragment", None),
        ("one\\x.png", None),
        ("one\x00.png", None),
        (None, None),
        ("", None),
    ],
)
def test_mapping_uses_web_policy_without_reading_other_paths(reference, expected):
    assert mapped_asset_name(reference) == expected


def test_asset_inventory_keeps_format_hashes_separate_and_does_not_follow_symlinks(tmp_path):
    assets = make_assets(tmp_path)
    (assets / "one.png").write_bytes(b"\x89PNG\r\n\x1a\nfictional-png")
    (assets / "copy.webp").write_bytes((assets / "one.webp").read_bytes())
    (assets / "bad.webp").write_bytes(b"not-an-image")
    (assets / "bad.unknown").write_bytes(b"not-an-image")
    private = tmp_path / "outside.txt"
    private.write_text("do not read outside")
    (assets / "link.webp").symlink_to(private)
    (assets / "nested").mkdir()
    inventory, first_hash = file_inventory(assets)
    by_name = {entry["name"]: entry for entry in inventory}
    assert by_name["one.png"]["sha256"] != by_name["one.webp"]["sha256"]
    assert by_name["link.webp"]["status"] == "symlink_blocked"
    assert by_name["link.webp"]["sha256"] is None
    assert by_name["bad.webp"]["signature_matches_extension"] is False
    assert by_name["bad.unknown"]["signature_matches_extension"] is False
    report, rows = audit_seed(HEADER + ROW + ";", "d" * 64, inventory, first_hash)
    assert rows[0]["source_asset_sha256"] != rows[0]["mapped_asset_sha256"]
    # Byte equality also finds the two invalid files; it never proves image identity/permission.
    assert report["byte_identical_asset_groups"] == 2
    assert report["unused_read_assets"] == 4
    assert file_inventory(assets)[1] == first_hash
    (assets / "one.webp").write_bytes(b"RIFF\x00\x00\x00\x00WEBPchanged")
    assert file_inventory(assets)[1] != first_hash


def test_symlink_asset_root_is_rejected(tmp_path):
    assets = make_assets(tmp_path)
    link = tmp_path / "linked-directory"
    link.symlink_to(assets, target_is_directory=True)
    with pytest.raises(AuditError, match="asset_root_must_be_real_directory"):
        file_inventory(link)


def test_asset_byte_budgets_hold_large_files_without_hashing_them(tmp_path, monkeypatch):
    import pubburi_recommendation.legacy_seed_audit as module

    assets = make_assets(tmp_path)
    monkeypatch.setattr(module, "MAX_ASSET_BYTES", 8)
    inventory, _ = file_inventory(assets)
    assert inventory[0]["status"] == "oversized_blocked" and inventory[0]["sha256"] is None
    monkeypatch.setattr(module, "MAX_ASSET_BYTES", 100)
    monkeypatch.setattr(module, "MAX_TOTAL_ASSET_BYTES", 8)
    with pytest.raises(AuditError, match="asset_inventory_exceeds_128_mib"):
        file_inventory(assets)


@pytest.mark.parametrize("stale_size", [False, True])
def test_oversized_assets_never_read_past_total_budget(tmp_path, monkeypatch, stale_size):
    from types import SimpleNamespace

    import pubburi_recommendation.legacy_seed_audit as module

    assets = tmp_path / "assets"
    assets.mkdir()
    for index in range(3):
        (assets / f"large-{index}.webp").write_bytes(b"x" * 9)
    monkeypatch.setattr(module, "MAX_ASSET_BYTES", 8)
    monkeypatch.setattr(module, "MAX_TOTAL_ASSET_BYTES", 16)
    original_fdopen, original_read, original_fstat = (
        module.os.fdopen,
        module.os.read,
        module.os.fstat,
    )
    observed = {"bytes": 0}

    class CountingReader:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def fileno(self):
            return self.stream.fileno()

        def read(self, size):
            chunk = self.stream.read(size)
            observed["bytes"] += len(chunk)
            return chunk

    def counted_read(descriptor, size):
        chunk = original_read(descriptor, size)
        observed["bytes"] += len(chunk)
        return chunk

    def reported_stat(descriptor):
        actual = original_fstat(descriptor)
        return SimpleNamespace(
            st_mode=actual.st_mode,
            st_size=0,
            st_mtime_ns=actual.st_mtime_ns,
            st_ctime_ns=actual.st_ctime_ns,
        )

    monkeypatch.setattr(
        module.os,
        "fdopen",
        lambda *args, **kwargs: CountingReader(original_fdopen(*args, **kwargs)),
    )
    monkeypatch.setattr(module.os, "read", counted_read)
    if stale_size:
        monkeypatch.setattr(module.os, "fstat", reported_stat)
    try:
        file_inventory(assets)
    except AuditError:
        pass  # Growing/changed sources may be held; actual I/O must still respect the cap.
    assert observed["bytes"] <= 16
    if not stale_size:
        assert observed["bytes"] == 0  # fstat rejects known oversize before any body read.


def test_manifest_cannot_turn_inventory_into_automatic_training_permission():
    manifest = json.loads((ROOT / "sources/legacy-demo-seed.json").read_text())
    LegacyManifest.model_validate(manifest)
    manifest["structured_feature_fit_approved"] = True
    with pytest.raises(ValueError):
        LegacyManifest.model_validate(manifest)


def test_cli_only_writes_new_private_outputs_without_user_rows_or_values_in_errors(tmp_path):
    assets = make_assets(tmp_path)
    source = tmp_path / "seed.sql"
    source.write_text(
        "INSERT INTO t_user VALUES ('private-user@example.invalid','not-a-real-password');"
        + HEADER
        + ROW
        + ";"
    )
    output = tmp_path / ".pubburi" / "audit"
    command = [
        sys.executable,
        "-m",
        "pubburi_recommendation.legacy_seed_audit",
        "--manifest",
        str(ROOT / "sources/legacy-demo-seed.json"),
        "--sql",
        str(source),
        "--assets-dir",
        str(assets),
        "--output-dir",
        str(output),
    ]
    first = subprocess.run(command, capture_output=True, text=True, check=False)
    assert first.returncode == 0, first.stderr
    for file in output.iterdir():
        assert (
            "private-user" not in file.read_text() and "not-a-real-password" not in file.read_text()
        )
    assert "fixture bottle" not in first.stdout  # Summary stdout contains no product rows.
    before = (output / "audit-report.json").read_bytes()
    second = subprocess.run(command, capture_output=True, text=True, check=False)
    assert second.returncode == 2 and "existing_audit_must_be_preserved" in second.stderr
    assert (output / "audit-report.json").read_bytes() == before
    command[-1] = str(tmp_path / "public")
    denied = subprocess.run(command, capture_output=True, text=True, check=False)
    assert denied.returncode == 2 and not (tmp_path / "public").exists()
    command[-1] = str(tmp_path / ".pubburi" / "bad-source")
    source.write_text(HEADER + "('private-product-value','x',SOME_FUNCTION(),'',0,0);")
    invalid = subprocess.run(command, capture_output=True, text=True, check=False)
    assert invalid.returncode == 2 and "private-product-value" not in invalid.stderr
    assert not Path(command[-1]).exists()
