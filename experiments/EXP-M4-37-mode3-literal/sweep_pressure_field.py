#!/usr/bin/env python3

"""Sweep one pressure-shader literal field and summarize full-frame hashes."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import subprocess


def main():
   parser = argparse.ArgumentParser()
   parser.add_argument("variant_dir", type=Path)
   parser.add_argument("prefix")
   parser.add_argument("output", type=Path)
   args = parser.parse_args()
   records = []
   for value in range(256):
      archive = args.variant_dir / f"{args.prefix}{value:02x}.bin"
      result = subprocess.run(
         ["./agxrender", "--archive", str(archive), "--source",
          "kernels/mode3.metal", "--vertex", "vertex_literal_pressure",
          "--fragment", "fragment_literal_pressure", "--width", "8",
          "--height", "8"], text=True, capture_output=True, timeout=8.0)
      lines = result.stdout.splitlines()
      status = next((x.removeprefix("STATUS ") for x in lines
                     if x.startswith("STATUS ")), "MISSING")
      pixels = [bytes.fromhex(x.split("bgra=", 1)[1].split()[0])
                for x in lines if x.startswith("PIXEL ")]
      records.append({"value": value, "status": status,
                      "returncode": result.returncode,
                      "sha256": hashlib.sha256(b"".join(pixels)).hexdigest()
                      if pixels else None})
   args.output.write_text(json.dumps(records, indent=2) + "\n")
   groups = defaultdict(list)
   for record in records:
      groups[(record["status"], record["sha256"])].append(record["value"])
   for key, values in sorted(groups.items(), key=lambda item: -len(item[1])):
      print(f"count={len(values)} status={key[0]} sha256={key[1]} "
            f"values={' '.join(f'{x:02x}' for x in values)}")


if __name__ == "__main__":
   main()
