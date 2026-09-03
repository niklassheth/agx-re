#!/usr/bin/env python3
"""Hold the native load fixed and sweep only FALU2I bits 45--47."""

from __future__ import annotations

import json
import pathlib
import subprocess

import run_remote as cross


ROOT = pathlib.Path(__file__).resolve().parent


def main() -> int:
    native = cross.extract_main()
    load_offset, consumer_offset = cross.locate_instructions(native)
    records = []
    for selector in range(8):
        command = cross.base_command()
        command += ["--splice", cross.consumer_splice(
            native, consumer_offset, selector)]
        process = cross.invoke(command)
        status, values = cross.parse_output(process)
        record = {
            "selector": selector,
            "status": status,
            "values": values,
            "oracle": cross.ORACLE_BITS,
            "exact": status == "OK" and values == cross.ORACLE_BITS,
            "returncode": process.returncode,
            "stdout": process.stdout,
            "stderr": process.stderr,
        }
        records.append(record)
        print(f"native-token selector={selector} exact={int(record['exact'])} "
              f"status={status} values={values}", flush=True)

    payload = {
        "schema_version": 1,
        "native_main_hex": native.hex(),
        "load_offset": load_offset,
        "native_producer_bytes": native[load_offset + 8:load_offset + 10].hex(),
        "consumer_offset": consumer_offset,
        "records": records,
    }
    (ROOT / "NATIVE_SELECTOR_RESULTS.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n")
    exact = [record["selector"] for record in records if record["exact"]]
    print(f"SUMMARY exact_selectors={exact}")
    return 0 if exact == [6] else 1


if __name__ == "__main__":
    raise SystemExit(main())
