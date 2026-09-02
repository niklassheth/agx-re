#!/usr/bin/env python3

"""Run vertex mode-3 variants and hash the complete render target."""

import argparse
import hashlib
from pathlib import Path
import subprocess


def main():
   parser = argparse.ArgumentParser()
   parser.add_argument("variant_dir", type=Path)
   parser.add_argument("names", nargs="*")
   parser.add_argument("--timeout", type=float, default=8.0)
   parser.add_argument("--size", type=int, default=8)
   args = parser.parse_args()

   names = args.names or sorted(path.stem for path in args.variant_dir.glob("*.bin"))
   for name in names:
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
         print(f"{name}\tTIMEOUT")
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
      digest = hashlib.sha256(image).hexdigest() if pixels else "MISSING"
      unique = len(set(pixels))
      error = next((line for line in lines if line.startswith("ERROR ")), "")
      print(
         f"{name}\t{result.returncode}\t{status}\t{digest}\t"
         f"pixels={len(pixels)} unique={unique}\t{error}"
      )


if __name__ == "__main__":
   main()
