#!/usr/bin/env python3

"""Cross literal destination, mode-3 tail selector, and vertex-store source."""

import argparse
import importlib.util
from pathlib import Path


def load_agxparse(path):
   spec = importlib.util.spec_from_file_location("agxparse", path)
   module = importlib.util.module_from_spec(spec)
   spec.loader.exec_module(module)
   return module


def set_destination(code, offset, destination):
   code[offset] = (code[offset] & 0x0f) | ((destination & 0x0f) << 4)
   code[offset + 2] = (code[offset + 2] & 0x1f) | ((destination >> 4) << 5)


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
   if len(literals) != 2:
      raise SystemExit(f"expected two mode-3 literals, found {literals}")

   # The fourth position vary-store (slot 3) consumes w.  Its byte +3 is the
   # ordinary `(source GPR << 1)` descriptor established by prior VS tests.
   w_store = None
   for offset in range(len(main_bytes) - 7):
      word = main_bytes[offset : offset + 8]
      if word[0] != 0x57:
         continue
      slot = (word[4] >> 5) | ((word[5] & 1) << 3)
      if slot == 3:
         w_store = offset
         break
   if w_store is None:
      raise SystemExit("position-w vary_store not found")

   args.output.mkdir(parents=True, exist_ok=True)
   literal = literals[1]
   for destination in range(16, 32):
      for source in range(16):
         code = bytearray(main_bytes)
         set_destination(code, literal, destination)
         code[w_store + 3] = source << 1
         output = bytearray(original)
         output[base : base + length] = code
         (args.output / f"dst_{destination:02d}_src_{source:02d}.bin").write_bytes(output)

   for tail in range(8):
      for source in range(16):
         code = bytearray(main_bytes)
         code[literal + 9] = tail << 5
         code[w_store + 3] = source << 1
         output = bytearray(original)
         output[base : base + length] = code
         (args.output / f"tail_{tail}_src_{source:02d}.bin").write_bytes(output)

   print(f"main={base:#x}+{length:#x} literal={literal:#x} w_store={w_store:#x}")


if __name__ == "__main__":
   main()
