#!/usr/bin/env python3

"""Execute destination/source mapping variants and report non-clear results."""

import argparse
import hashlib
from pathlib import Path
import subprocess


CLEAR = "5341e6b2646979a70e57653007a1f310169421ec9bdd9f1a5648f75ade005af1"
BASELINE = "908aa8b3fe5cf5879f477eb694d947a1189b19a67b31ae032bf1cf861f03e270"


def main():
   parser = argparse.ArgumentParser()
   parser.add_argument("variant_dir", type=Path)
   args = parser.parse_args()

   outcomes = {}
   for archive in sorted(args.variant_dir.glob("*.bin")):
      result = subprocess.run(
         ["./agxrender", "--archive", str(archive), "--source",
          "kernels/mode3.metal", "--vertex", "vertex_mode3", "--fragment",
          "fragment_mode3", "--width", "8", "--height", "8"],
         text=True, capture_output=True, timeout=8.0)
      lines = result.stdout.splitlines()
      status = next((x.removeprefix("STATUS ") for x in lines
                     if x.startswith("STATUS ")), "MISSING")
      pixels = [bytes.fromhex(x.split("bgra=", 1)[1].split()[0])
                for x in lines if x.startswith("PIXEL ")]
      digest = hashlib.sha256(b"".join(pixels)).hexdigest() if pixels else None
      outcomes.setdefault((status, digest), []).append(archive.stem)

   for (status, digest), names in sorted(outcomes.items(), key=lambda x: -len(x[1])):
      label = "BASELINE" if digest == BASELINE else "CLEAR" if digest == CLEAR else "OTHER"
      print(f"{label} status={status} sha256={digest} count={len(names)}")
      print(" ".join(names))


if __name__ == "__main__":
   main()
