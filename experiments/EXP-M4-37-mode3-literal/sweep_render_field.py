#!/usr/bin/env python3

"""Sweep one generated render field and summarize exact output classes."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess


def main():
   parser = argparse.ArgumentParser()
   parser.add_argument("variant_dir", type=Path)
   parser.add_argument("prefix")
   parser.add_argument("output", type=Path)
   parser.add_argument("--timeout", type=float, default=8.0)
   parser.add_argument("--size", type=int, default=8)
   args = parser.parse_args()

   records = []
   for value in range(256):
      name = f"{args.prefix}{value:02x}"
      command = [
         "./agxrender",
         "--archive",
         str(args.variant_dir / f"{name}.bin"),
         "--source",
         "kernels/mode3.metal",
         "--vertex",
         "vertex_mode3",
         "--fragment",
         "fragment_mode3",
         "--width",
         str(args.size),
         "--height",
         str(args.size),
      ]
      try:
         result = subprocess.run(
            command, text=True, capture_output=True, timeout=args.timeout
         )
      except subprocess.TimeoutExpired:
         records.append({"value": value, "status": "TIMEOUT"})
         continue

      lines = result.stdout.splitlines()
      status = next(
         (line.removeprefix("STATUS ") for line in lines if line.startswith("STATUS ")),
         "MISSING",
      )
      pixels = [
         bytes.fromhex(line.split("bgra=", 1)[1].split()[0])
         for line in lines
         if line.startswith("PIXEL ")
      ]
      image = b"".join(pixels)
      records.append(
         {
            "value": value,
            "status": status,
            "returncode": result.returncode,
            "sha256": hashlib.sha256(image).hexdigest() if pixels else None,
            "unique_pixels": len(set(pixels)),
         }
      )

   args.output.write_text(json.dumps(records, indent=2) + "\n")
   classes = defaultdict(list)
   for record in records:
      key = (record.get("status"), record.get("sha256"), record.get("unique_pixels"))
      classes[key].append(record["value"])
   for key, values in sorted(classes.items(), key=lambda item: (-len(item[1]), item[0])):
      print(
         f"count={len(values)} status={key[0]} sha256={key[1]} unique={key[2]} "
         f"values={' '.join(f'{value:02x}' for value in values)}"
      )


if __name__ == "__main__":
   main()
