"""Installed checked-export consumer/CLI over the owned ephemeral B1 HTTP server."""

import json
import subprocess
from pathlib import Path


def smoke_checked_provider_http(python, work, base_url):
    context = json.loads((work / "provider-acceptance-context.json").read_text())
    output = work / ".pubburi" / "checked-provider-http"
    args = {
        **context["arguments"],
        "export-dir": context["export-dir"],
        "spec": context["spec"],
        "base-url": base_url,
        "output-dir": output,
    }

    def run(values, extra=()):
        command = [str(python), "-I", "-m", "pubburi_recommendation.reviewed_provider_acceptance"]
        for key, value in values.items():
            command += ["--" + key, str(value)]
        return subprocess.run(
            command + list(extra), cwd=work, capture_output=True, text=True, timeout=60
        )

    result = run(args)
    if result.returncode != 0:
        raise RuntimeError("Installed checked-export provider HTTP CLI failed")
    report = json.loads((output / "acceptance-report.json").read_text())
    if (
        not report["passed"]
        or report["passed_contract_cases"] != 5
        or (
            report["checked_export"]["mode"] != "fresh_demo_snapshot"
            or report["checked_export"]["service_catalog_approved"]
            or report["checked_export"]["model_loaded"]
        )
    ):
        raise RuntimeError("Installed checked provider changed facts, mode or authority")
    replay = work / ".pubburi" / "checked-provider-replay"
    if run({**args, "output-dir": replay}, ("--replay",)).returncode != 0:
        raise RuntimeError("Installed explicit provider replay failed")
    replay_report = json.loads((replay / "acceptance-report.json").read_text())
    if replay_report["checked_export"]["mode"] != "historical_demo_replay":
        raise RuntimeError("Installed provider replay pretended to be fresh")
    request = Path(context["export-dir"]) / "b1-demo-request.json"
    original = request.read_bytes()
    request.write_bytes(original + b" ")
    rejected_output = work / ".pubburi" / "checked-provider-tampered"
    try:
        rejected = run({**args, "output-dir": rejected_output})
        if (
            rejected.returncode != 2
            or rejected_output.exists()
            or ("checked_export_artifact_bytes_conflict" not in rejected.stderr)
        ):
            raise RuntimeError("Installed provider consumed a changed completed request artifact")
    finally:
        request.write_bytes(original)
