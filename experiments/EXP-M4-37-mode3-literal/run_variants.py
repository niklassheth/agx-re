#!/usr/bin/env python3

"""Run mode-3 archive variants through the experiment's texture fixture."""

import argparse
from pathlib import Path
import subprocess


def main():
   parser = argparse.ArgumentParser()
   parser.add_argument("variant_dir", type=Path)
   parser.add_argument("function")
   parser.add_argument("mode", choices=("read", "write"))
   parser.add_argument("names", nargs="*")
   parser.add_argument("--timeout", type=float, default=8.0)
   args = parser.parse_args()

   names = args.names or sorted(path.stem for path in args.variant_dir.glob("*.bin"))
   for name in names:
      command = [
         "./texcomp",
         "--archive",
         str(args.variant_dir / f"{name}.bin"),
         "--source",
         "kernels/mode3.metal",
         "--function",
         args.function,
         "--mode",
         args.mode,
      ]
      if args.mode == "read":
         command.append("--sampler")

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
      prefix = "OUT 0 " if args.mode == "read" else "TEXEL 0 "
      observable = next(
         (line.removeprefix(prefix) for line in lines if line.startswith(prefix)),
         "MISSING",
      )
      error = next((line for line in lines if line.startswith("ERROR ")), "")
      print(f"{name}\t{result.returncode}\t{status}\t{observable}\t{error}")


if __name__ == "__main__":
   main()
