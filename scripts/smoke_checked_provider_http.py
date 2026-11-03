"""Installed checked-export consumer/CLI over the owned ephemeral B1 HTTP server."""

import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener


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
        or report["passed_contract_cases"] != 6
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
    # A controlled owned-loopback intermediary forwards the real installed service.
    # Its explicit faults exercise the CLI, including the no-items feedback case.
    for mode in ("metadata", "spec_changed", "spec_deleted"):
        copied_spec = work / ("provider-fault-" + mode + ".json")
        copied_spec.write_bytes(Path(context["spec"]).read_bytes())
        state = {"calls": 0}

        class FaultHandler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                content = self.rfile.read(int(self.headers["Content-Length"]))
                request = Request(
                    base_url + self.path, data=content, headers={"Content-Type": "application/json"}
                )
                with build_opener(ProxyHandler({})).open(request, timeout=30) as response:
                    value = json.load(response)
                state["calls"] += 1
                if mode == "metadata" and self.path.endswith("/feedback"):
                    value["positive_references"] = []
                    value["not_interested_references"] = []
                if state["calls"] == 1 and mode == "spec_changed":
                    copied_spec.write_bytes(copied_spec.read_bytes() + b" ")
                if state["calls"] == 1 and mode == "spec_deleted":
                    copied_spec.unlink()
                encoded = json.dumps(value).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        with ThreadingHTTPServer(("127.0.0.1", 0), FaultHandler) as proxy:
            thread = threading.Thread(target=proxy.serve_forever, daemon=True)
            thread.start()
            fault_output = work / ".pubburi" / ("provider-fault-" + mode)
            try:
                fault = run(
                    {
                        **args,
                        "base-url": f"http://127.0.0.1:{proxy.server_port}",
                        "spec": copied_spec,
                        "output-dir": fault_output,
                    }
                )
            finally:
                proxy.shutdown()
                thread.join(timeout=5)
        receipt = json.loads((fault_output / "receipt.json").read_text())
        if mode == "metadata":
            failed = json.loads((fault_output / "acceptance-report.json").read_text())
            blocked = next(
                case for case in failed["cases"] if case["case_id"] == "feedback-blocked-empty"
            )
            if (
                fault.returncode != 1
                or receipt["completed"] is not True
                or failed["passed"]
                or blocked["passed"]
            ):
                raise RuntimeError(
                    "Installed CLI approved feedback reference faults with empty results"
                )
        elif (
            fault.returncode != 2
            or receipt["completed"] is not False
            or (fault_output / "acceptance-report.json").exists()
        ):
            raise RuntimeError("Installed CLI completed after its frozen spec changed/disappeared")
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
