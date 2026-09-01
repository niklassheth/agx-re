#!/usr/bin/env python3
"""Run EXP-M4-36 with exact full-buffer readback and per-case watchdogs."""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import time


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
AGXTEST = REPO / "tools" / "agxtest" / "agxtest.py"


def parse_result(stdout: str) -> tuple[str, list[int] | None]:
    status = "UNKNOWN"
    values = None
    for line in stdout.splitlines():
        if line.startswith("STATUS "):
            status = line.split(None, 1)[1]
        elif line.startswith("RESULT 0 "):
            values = [int(value) for value in line.split()[2:]]
    return status, values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=25.0)
    args = parser.parse_args()

    subprocess.run(["python3", str(HERE / "generate.py")], check=True)
    spec = json.loads((HERE / "generated" / "cases.json").read_text())
    root = HERE / "captures" / args.run_id
    root.mkdir(parents=True, exist_ok=True)
    work = root / "work"
    work.mkdir(exist_ok=True)
    records = []

    input_out = ",".join(str(value) for value in spec["initial_output"])
    input_mem = ",".join(str(value) for value in spec["inputs"])
    first = True
    for case in spec["cases"]:
        hangs = 0
        for repetition in range(1, args.repetitions + 1):
            command = [
                "python3", str(AGXTEST),
                "--source", str(HERE / "carrier.metal"),
                "--function", "k",
                "--grid", "1",
                "--tg", "1",
                "--int",
                "--buf", f"0={input_out}",
                "--buf", f"1={input_mem}",
                "--out", "0=5",
                "--workdir", str(work),
                "--run-timeout", str(args.timeout),
                "--splice", f"_agc.main@0={case['program']}",
            ]
            if first:
                command.append("--rebuild")
                first = False
            started = time.monotonic()
            timed_out = False
            try:
                process = subprocess.run(
                    command, text=True, capture_output=True,
                    timeout=args.timeout + 15.0)
                stdout = process.stdout
                stderr = process.stderr
                returncode = process.returncode
            except subprocess.TimeoutExpired as error:
                stdout = error.stdout or ""
                stderr = error.stderr or ""
                returncode = None
                timed_out = True

            status, values = parse_result(stdout)
            canary_ok = bool(values and
                             values[spec["canary_index"]] == spec["canary_value"])
            observed = None if values is None else values[:len(
                case["predicted_associative_output"])]
            associative_match = (
                observed == case["predicted_associative_output"]
                if observed is not None else False)
            outcome = (
                "hang" if timed_out or status == "HANG" else
                "fault" if status == "CMDBUF_ERROR" else
                "exact_associative" if status == "OK" and canary_ok and associative_match else
                "changed_output" if status == "OK" and canary_ok else
                "invalid_no_canary" if status == "OK" else
                "harness_failure"
            )
            record = {
                "case": case["id"],
                "repetition": repetition,
                "status": status,
                "outcome": outcome,
                "returncode": returncode,
                "elapsed_seconds": time.monotonic() - started,
                "values": values,
                "observed": observed,
                "predicted_associative_output":
                    case["predicted_associative_output"],
                "canary_ok": canary_ok,
                "metadata": {key: value for key, value in case.items()
                             if key not in ("program",)},
            }
            case_root = root / case["id"] / f"repeat-{repetition}"
            case_root.mkdir(parents=True, exist_ok=True)
            (case_root / "stdout.log").write_text(stdout)
            (case_root / "stderr.log").write_text(stderr)
            (case_root / "result.json").write_text(
                json.dumps(record, indent=2, sort_keys=True) + "\n")
            records.append(record)
            print(f"{case['id']} repeat={repetition} {outcome} {observed}",
                  flush=True)
            if outcome == "hang":
                hangs += 1
                if hangs == 2:
                    print(f"STOP {case['id']} after two hangs", flush=True)
                    break

    (root / "results.json").write_text(json.dumps({
        "schema_version": 1,
        "run_id": args.run_id,
        "records": records,
    }, indent=2, sort_keys=True) + "\n")
    controls = [record for record in records
                if record["metadata"].get("expected") == "exact"]
    bad_controls = [record for record in controls
                    if record["outcome"] != "exact_associative"]
    print(json.dumps({
        "records": len(records),
        "bad_controls": len(bad_controls),
        "associative_exact": sum(record["outcome"] == "exact_associative"
                                 for record in records),
        "faults": sum(record["outcome"] == "fault" for record in records),
        "hangs": sum(record["outcome"] == "hang" for record in records),
    }, sort_keys=True))
    return int(bool(bad_controls))


if __name__ == "__main__":
    raise SystemExit(main())
