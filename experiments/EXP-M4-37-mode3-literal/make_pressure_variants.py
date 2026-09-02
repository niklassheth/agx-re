#!/usr/bin/env python3

"""Ablate every mode-3 tail in the all-live vertex literal pressure shader."""

import argparse
import importlib.util
from pathlib import Path


def load_agxparse(path):
   spec = importlib.util.spec_from_file_location("agxparse", path)
   module = importlib.util.module_from_spec(spec)
   spec.loader.exec_module(module)
   return module


def main():
   parser = argparse.ArgumentParser()
   parser.add_argument("archive", type=Path)
   parser.add_argument("agxparse", type=Path)
   parser.add_argument("output", type=Path)
   args = parser.parse_args()

   agxparse = load_agxparse(args.agxparse)
   original = args.archive.read_bytes()
   base, length = agxparse.locate_region(original, "_agc.main", stage="vertex")
   main_bytes = original[base : base + length]
   literals = []
   for offset in range(len(main_bytes) - 9):
      word = main_bytes[offset : offset + 10]
      if ((word[0] & 0x0f) == 0x0c and word[1] in (0x80, 0x84)
          and (word[2] & 0x1f) == 3 and word[8] == 0x40):
         literals.append(offset)
   if not literals:
      raise SystemExit("no mode-3 literals")

   args.output.mkdir(parents=True, exist_ok=True)
   (args.output / "literal_offsets.txt").write_text(
      "\n".join(f"{x:#x}" for x in literals) + "\n")

   variants = {"control": {}}
   for i, offset in enumerate(literals):
      for value in range(8):
         variants[f"lit_{i:02d}_field_{value}"] = {offset + 9: value << 5}
      variants[f"lit_{i:02d}_b1_bit2"] = {offset + 9: main_bytes[offset + 9] ^ 4}
      for value in (0x20, 0x40, 0x41, 0x60, 0x80, 0xc0, 0xc1):
         variants[f"lit_{i:02d}_b0_{value:02x}"] = {offset + 8: value}

   # Dense representatives for an even and odd destination register.  This
   # isolates the parity-sensitive byte-9 bit found by the sparse sweep.
   for i in (2, 3):
      offset = literals[i]
      for value in range(256):
         variants[f"dense_lit_{i:02d}_b0_{value:02x}"] = {offset + 8: value}
         variants[f"dense_lit_{i:02d}_b1_{value:02x}"] = {offset + 9: value}

   for name, mutations in variants.items():
      output = bytearray(original)
      for offset, value in mutations.items():
         output[base + offset] = value
      (args.output / f"{name}.bin").write_bytes(output)
   print(f"main={base:#x}+{length:#x} literals={len(literals)} variants={len(variants)}")


if __name__ == "__main__":
   main()
