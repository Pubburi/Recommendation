#!/usr/bin/env python3
"""Build and run the published wheel without the checkout or development dependencies."""

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEALTH = {"status": "ok", "service": "pubburi-recommendation"}


def run(uv: str, *args: str, cwd: Path = ROOT, stdout: int | None = None) -> None:
    subprocess.run([uv, *args], cwd=cwd, stdout=stdout, check=True, timeout=180)


def request_json(
    base_url: str, path: str, *, body: dict | None = None, expected_status: int = 200
) -> dict:
    # Local verification must not depend on a developer's HTTP proxy configuration.
    request = Request(
        base_url + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={} if body is None else {"Content-Type": "application/json"},
    )
    try:
        response = build_opener(ProxyHandler({})).open(request, timeout=1)
    except HTTPError as error:
        if error.code != expected_status:
            raise
        response = error
    with response:
        if (
            response.status != expected_status
            or response.headers.get_content_type() != "application/json"
        ):
            raise RuntimeError(f"Unexpected HTTP response for {path}")
        return json.load(response)


def verify_http(python: Path, work: Path) -> None:
    # Keep the ephemeral port reserved until Uvicorn receives this exact socket.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        runtime_env = {
            key: value
            for key, value in os.environ.items()
            if key in {"PATH", "LANG", "LC_ALL", "SYSTEMROOT", "TMP", "TEMP", "TMPDIR"}
        }
        with (work / "uvicorn.log").open("w+") as log:
            process = subprocess.Popen(
                [
                    str(python),
                    "-I",
                    "-m",
                    "uvicorn",
                    "pubburi_recommendation.main:app",
                    "--fd",
                    str(listener.fileno()),
                    "--no-access-log",
                ],
                cwd=work,
                env=runtime_env,
                pass_fds=(listener.fileno(),),
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                base_url = f"http://127.0.0.1:{port}"
                deadline = time.monotonic() + 30
                while True:
                    if process.poll() is not None:
                        raise RuntimeError("The installed wheel exited before becoming ready")
                    try:
                        health = request_json(base_url, "/health")
                        break
                    except (URLError, TimeoutError):
                        if time.monotonic() >= deadline:
                            raise RuntimeError("The installed wheel did not become ready") from None
                        time.sleep(0.1)

                if health != EXPECTED_HEALTH:
                    raise RuntimeError("The installed wheel violated the /health contract")
                schema = request_json(base_url, "/openapi.json")
                response = schema["paths"]["/health"]["get"]["responses"]["200"]
                if response["content"]["application/json"]["schema"]["type"] != "object":
                    raise RuntimeError("The installed wheel did not document its JSON health API")
                path = "/v1/recommendations/baseline"
                if "post" not in schema["paths"].get(path, {}):
                    raise RuntimeError("The installed wheel did not document its baseline API")
                result = request_json(
                    base_url,
                    path,
                    body={
                        "catalog": [
                            {"product_id": 3, "available": True, "price_krw": 1000},
                            {"product_id": 1, "available": False, "price_krw": 1000},
                            {"product_id": 2, "available": True},
                        ],
                        "constraints": {"max_price_krw": 1000},
                    },
                )
                expected = {
                    "algorithm": "b0-id-ascending-v1",
                    "items": [
                        {
                            "product_id": 3,
                            "reasons": [
                                "available",
                                "price_within_range",
                                "deterministic_baseline",
                            ],
                        }
                    ],
                    "eligible_count": 1,
                    "fallback_reason": None,
                }
                if result != expected:
                    raise RuntimeError("The installed wheel violated baseline eligibility")
                rejected = request_json(
                    base_url,
                    path,
                    body={
                        "catalog": [{"product_id": 1, "available": True}] * 2,
                    },
                    expected_status=422,
                )
                if not rejected.get("detail"):
                    raise RuntimeError("The installed wheel accepted duplicate catalog IDs")
                print("Installed wheel passed isolated health, baseline and OpenAPI verification.")
            except BaseException:
                log.flush()
                log.seek(0)
                print(log.read()[-4000:], file=sys.stderr)
                raise
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


def main(progress: dict[str, str]) -> None:
    if os.name != "posix":
        raise SystemExit("The distribution smoke supports the Linux/macOS development targets.")
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("Install the pinned uv version before running distribution verification.")

    with tempfile.TemporaryDirectory(prefix="pubburi-wheel-") as temp:
        work = Path(temp)
        built = work / "dist"
        requirements = work / "runtime.txt"
        progress["stage"] = "build-sdist-and-wheel"
        run(uv, "build", "--no-sources", "--out-dir", str(built))
        wheels = list(built.glob("*.whl"))
        sdists = list(built.glob("*.tar.gz"))
        if len(wheels) != 1 or len(sdists) != 1:
            raise RuntimeError("Expected exactly one fresh wheel and source distribution")
        progress["stage"] = "export-locked-runtime"
        run(
            uv,
            "export",
            "--locked",
            "--no-dev",
            "--no-default-groups",
            "--no-emit-project",
            "--no-sources",
            "--no-header",
            "--no-annotate",
            "--output-file",
            str(requirements),
            stdout=subprocess.DEVNULL,
        )
        venv = work / "runtime"
        progress["stage"] = "install-runtime-and-wheel"
        run(uv, "venv", "--python", sys.executable, "--no-python-downloads", str(venv))
        python = venv / "bin" / "python"
        run(
            uv,
            "pip",
            "install",
            "--python",
            str(python),
            "--require-hashes",
            "--no-deps",
            "-r",
            str(requirements),
        )
        run(uv, "pip", "install", "--python", str(python), "--no-deps", str(wheels[0]))
        run(uv, "pip", "check", "--python", str(python))
        progress["stage"] = "isolated-wheel-import"
        probe = (
            "import pathlib, sys; import pubburi_recommendation.main as m; "
            "assert pathlib.Path(m.__file__).resolve().is_relative_to("
            "pathlib.Path(sys.prefix).resolve()), 'Wheel imported outside its isolated environment'"
        )
        subprocess.run([str(python), "-I", "-c", probe], cwd=work, check=True, timeout=10)
        progress["stage"] = "isolated-catalog-cli"
        subprocess.run(
            [str(python), "-I", "-m", "pubburi_recommendation.catalog_audit", "--help"],
            cwd=work,
            check=True,
            timeout=10,
            stdout=subprocess.DEVNULL,
        )
        progress["stage"] = "isolated-wikidata-offline-replay"
        # Actual installed CLI, authored payloads only; CI never calls the external source.
        source_manifest = work / "wikidata-manifest.json"
        shutil.copy2(ROOT / "sources/wikidata-structured.json", source_manifest)
        source_payload = work / "authored-entity.json"
        source_payload.write_text(
            json.dumps(
                {
                    "success": 1,
                    "entities": {
                        "Q1": {
                            "id": "Q1",
                            "type": "item",
                            "lastrevid": 7,
                            "labels": {"mul": {"value": "authored contract fixture only"}},
                            "claims": {},
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        source_output = work / ".pubburi" / "source-replay"
        replay_command = [
            str(python),
            "-I",
            "-m",
            "pubburi_recommendation.wikidata_collect",
            "--manifest",
            str(source_manifest),
            "--ids",
            "Q1",
            "--snapshot",
            str(source_payload),
            "--output-dir",
            str(source_output),
        ]
        subprocess.run(replay_command, cwd=work, check=True, timeout=10, stdout=subprocess.DEVNULL)
        source_receipt = json.loads((source_output / "receipt.json").read_text(encoding="utf-8"))
        source_records = json.loads(
            (source_output / "normalized-records.json").read_text(encoding="utf-8")
        )
        if (
            not source_receipt["accepted"]
            or source_receipt["mode"] != "offline_replay"
            or source_receipt["http_status"] is not None
            or source_receipt["training_ready"]
            or source_records[0]["label"] != "authored contract fixture only"
            or source_records[0]["label_language"] != "mul"
        ):
            raise RuntimeError("The installed wheel violated the offline collection boundary")
        for suffix, rejected_body, expected_code in (
            ("maxlag", json.dumps({"error": {"code": "maxlag"}}), "api_maxlag"),
            (
                "depth",
                '{"x":' + "[" * 20000 + "0" + "]" * 20000 + "}",
                "json_nesting_exceeds_parser_limit",
            ),
        ):
            source_payload.write_text(rejected_body, encoding="utf-8")
            rejected_output = work / ".pubburi" / f"source-{suffix}"
            replay_command[-1] = str(rejected_output)
            rejected = subprocess.run(
                replay_command,
                cwd=work,
                check=False,
                timeout=10,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            rejected_receipt = json.loads(
                (rejected_output / "receipt.json").read_text(encoding="utf-8")
            )
            if (
                rejected.returncode != 2
                or rejected_receipt["accepted"]
                or rejected_receipt["error_code"] != expected_code
                or "Traceback" in rejected.stderr
                or (rejected_output / "normalized-records.json").exists()
            ):
                raise RuntimeError(
                    "The installed wheel treated a source error as an accepted catalog"
                )
        progress["stage"] = "isolated-legacy-inventory-cli"
        # Only tiny authored literals/byte signatures, never the real legacy seed or its images.
        legacy_manifest = work / "legacy-manifest.json"
        shutil.copy2(ROOT / "sources/legacy-demo-seed.json", legacy_manifest)
        legacy_sql = work / "authored-seed.sql"
        legacy_sql.write_text(
            "INSERT INTO t_product (name,type,price,img,abv,order_count) VALUES "
            "('fictional-smoke','fixture',1000,'authored.png',0,0);",
            encoding="utf-8",
        )
        legacy_assets = work / "authored-assets"
        legacy_assets.mkdir()
        (legacy_assets / "authored.webp").write_bytes(b"RIFF\x00\x00\x00\x00WEBPauthored-signature")
        legacy_output = work / ".pubburi" / "legacy-inventory"
        subprocess.run(
            [
                str(python),
                "-I",
                "-m",
                "pubburi_recommendation.legacy_seed_audit",
                "--manifest",
                str(legacy_manifest),
                "--sql",
                str(legacy_sql),
                "--assets-dir",
                str(legacy_assets),
                "--output-dir",
                str(legacy_output),
            ],
            cwd=work,
            check=True,
            timeout=10,
            stdout=subprocess.DEVNULL,
        )
        legacy_result = json.loads(
            (legacy_output / "audit-report.json").read_text(encoding="utf-8")
        )
        if (
            legacy_result["product_rows"] != 1
            or legacy_result["mapped_images_readable"] != 1
            or legacy_result["feature_fit_eligible_rows"] != 0
        ):
            raise RuntimeError(
                "The installed wheel violated the authored legacy inventory boundary"
            )
        progress["stage"] = "isolated-scenario-checker-cli"
        subprocess.run(
            [str(python), "-I", "-m", "pubburi_recommendation.scenario_evaluation", "--help"],
            cwd=work,
            check=True,
            timeout=10,
            stdout=subprocess.DEVNULL,
        )
        progress["stage"] = "isolated-content-fit"
        # Run actual fit/transform in the runtime-only wheel, not only import/--help.
        spec = work / "authored-content-spec.json"
        shutil.copy2(ROOT / "evaluation/content-fit-v1.json", spec)
        content_report = work / "reports" / "content-fit.json"
        subprocess.run(
            [
                str(python),
                "-I",
                "-m",
                "pubburi_recommendation.content_experiment",
                "--spec",
                str(spec),
                "--output",
                str(content_report),
            ],
            cwd=work,
            check=True,
            timeout=60,
            stdout=subprocess.DEVNULL,
        )
        content_result = json.loads(content_report.read_text(encoding="utf-8"))
        if (
            not content_result["passed_contract"]
            or content_result["data_kind"] != "authored_model_fixture"
            or content_result["fit_summary"]["vocabulary_size"] < 1
            or not content_result["fit_summary"]["numeric_fit"]["abv_percent"]["active"]
        ):
            raise RuntimeError(
                "The installed wheel did not fit and validate the authored B1 fixture"
            )
        progress["stage"] = "installed-wheel-http-contract"
        verify_http(python, work)
        # Preserve the normal local build outputs, but verify only this fresh build.
        progress["stage"] = "preserve-build-artifacts"
        (ROOT / "dist").mkdir(exist_ok=True)
        for artifact in [*wheels, *sdists]:
            shutil.copy2(artifact, ROOT / "dist" / artifact.name)
        progress["stage"] = "complete"


if __name__ == "__main__":
    # Convert graceful cancellation to an exception so owned process/temp cleanup runs.
    signal.signal(signal.SIGTERM, lambda signum, _frame: sys.exit(128 + signum))
    progress = {"stage": "preflight"}
    report = {"check": "installed-wheel", "python": sys.version.split()[0], "status": "failed"}
    try:
        main(progress)
        report["status"] = "passed"
    except BaseException as error:
        report["failure_kind"] = type(error).__name__
        raise
    finally:
        report.update(progress)
        reports = ROOT / "reports"
        reports.mkdir(exist_ok=True)
        (reports / "distribution-smoke.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
