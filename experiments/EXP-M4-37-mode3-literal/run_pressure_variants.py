#!/usr/bin/env python3

"""Run pressure-tail variants and group full-frame results."""

import argparse
from collections import defaultdict
import hashlib
from pathlib import Path
import subprocess


def main():
   parser = argparse.ArgumentParser()
   parser.add_argument("variant_dir", type=Path)
   args = parser.parse_args()
   groups = defaultdict(list)
   for archive in sorted(args.variant_dir.glob("*.bin")):
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
      digest = hashlib.sha256(b"".join(pixels)).hexdigest() if pixels else None
      groups[(status, digest, len(set(pixels)))].append(archive.stem)

   control = next((key for key, names in groups.items() if "control" in names), None)
   for key, names in sorted(groups.items(), key=lambda item: -len(item[1])):
      label = "BASELINE" if key == control else "OTHER"
      print(f"{label} status={key[0]} sha256={key[1]} unique={key[2]} count={len(names)}")
      print(" ".join(names))


if __name__ == "__main__":
   main()
