#!/usr/bin/env python3
"""Execute focused archive-input route mutations with complete output checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import time


HERE = pathlib.Path(__file__).resolve().parent


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify(stdout: str, returncode: int | None, timed_out: bool) -> str:
    if timed_out:
        return "hang"
    if "STATUS OK" in stdout and returncode == 0:
        return "exact"
    if "STATUS OUTPUT_MISMATCH" in stdout:
        return "changed_output"
    if "STATUS CMDBUF_ERROR" in stdout:
        return "fault"
    if "PIPELINE" in stdout or "ARCHIVE_FAIL" in stdout:
        return "pipeline_rejected"
    return "harness_failure"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("--suite", default="route_ablations")
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    generated = HERE / "generated" / args.suite
    manifest = json.loads((generated / "manifest.json").read_text())
    cases = {case["id"]: case for case in
             json.loads((generated / "cases.json").read_text())["cases"]}
    root = HERE / "captures" / args.suite.replace("_", "-") / args.run_id
    root.mkdir(parents=True, exist_ok=True)
    records = []
    for arm in manifest["arms"]:
        case = cases[arm["case"]]
        hangs = 0
        for repetition in range(1, args.repetitions + 1):
            case_root = root / arm["id"] / f"repeat-{repetition}"
            case_root.mkdir(parents=True, exist_ok=True)
            archive = HERE / arm["archive"]
            source = HERE / case["source"]
            expected = HERE / case["expected"]
            output = case_root / "output.bin"
            command = [
                str(HERE / "native_runner"),
                "--stage", "compute",
                "--source", str(source),
                "--archive-input", str(archive),
                "--output", str(output),
                "--expected", str(expected),
                "--compute", case["compute_function"],
                "--math-mode", case.get("math_mode", "precise"),
                "--dispatch-threads", str(case["dispatch_threads"]),
                "--threads-per-threadgroup",
                str(case["threads_per_threadgroup"]),
            ]
            started = time.monotonic()
            try:
                proc = subprocess.run(command, text=True, capture_output=True,
                                      timeout=args.timeout)
                stdout, stderr = proc.stdout, proc.stderr
                returncode = proc.returncode
                timed_out = False
            except subprocess.TimeoutExpired as error:
                stdout = error.stdout or ""
                stderr = error.stderr or ""
                returncode = None
                timed_out = True
            (case_root / "stdout.log").write_text(stdout)
            (case_root / "stderr.log").write_text(stderr)
            shutil.copy2(expected, case_root / "expected.bin")
            outcome = classify(stdout, returncode, timed_out)
            record = {
                "arm": arm["id"],
                "case": arm["case"],
                "route": arm["route"],
                "native_route": arm["native_route"],
                "rule": arm["rule"],
                "repetition": repetition,
                "outcome": outcome,
                "returncode": returncode,
                "elapsed_seconds": time.monotonic() - started,
                "pipeline_source_confirmed":
                    "PIPELINE_SOURCE archive-input" in stdout,
                "expected_sha256": sha(expected),
                "output_sha256": sha(output) if output.exists() else None,
            }
            (case_root / "result.json").write_text(
                json.dumps(record, indent=2, sort_keys=True) + "\n")
            records.append(record)
            print(f"{arm['id']} repeat={repetition} {outcome}", flush=True)
            if outcome == "hang":
                hangs += 1
                if hangs == 2:
                    print(f"STOP {arm['id']} after two hangs", flush=True)
                    break
    (root / "results.json").write_text(json.dumps({
        "schema_version": 1,
        "records": records,
    }, indent=2, sort_keys=True) + "\n")
    expected_by_arm = {arm["id"]: arm.get("expected")
                       for arm in manifest["arms"]}
    bad_controls = [record for record in records
                    if expected_by_arm[record["arm"]] == "exact" and
                    record["outcome"] != "exact"]
    source_failures = [record for record in records
                       if not record["pipeline_source_confirmed"] and
                       record["outcome"] not in ("hang", "pipeline_rejected")]
    print(json.dumps({
        "records": len(records),
        "bad_controls": len(bad_controls),
        "pipeline_source_failures": len(source_failures),
    }, sort_keys=True))
    return int(bool(bad_controls or source_failures))


if __name__ == "__main__":
    raise SystemExit(main())
