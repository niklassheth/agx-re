#!/usr/bin/env python3

"""Fit an extended raw literal into the native literal-store symbol."""

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
   base, length = agxparse.locate_region(original, "_agc.main", stage="compute")
   code = original[base : base + length]
   if length != 30:
      raise SystemExit(f"unexpected main length {length}")

   literal = bytearray(code[4:12])
   store = code[12:26]
   stop = code[26:30]
   args.output.mkdir(parents=True, exist_ok=True)

   def write(name, main):
      if len(main) != length:
         raise ValueError(len(main))
      output = bytearray(original)
      output[base : base + length] = main
      (args.output / f"{name}.bin").write_bytes(output)

   write("native", code)
   for mode in range(8):
      changed = bytearray(literal)
      changed[2] = (changed[2] & 0xe0) | mode
      for b0, b1 in ((0x00, 0x00), (0x40, 0x00), (0x40, 0x04),
                     (0x40, 0x60), (0xc0, 0x00), (0x20, 0x00)):
         # r1 = 0 is sufficient for the one-thread store index and frees the
         # two bytes occupied by the suffix of native get_sr.
         main = bytes((0x1c, 0x00)) + changed + bytes((b0, b1)) + store + stop
         write(f"mode_{mode}_tail_{b0:02x}{b1:02x}", main)

   for destination in (0, 2, 3, 8, 15, 16, 18, 19, 24, 31):
      changed = bytearray(literal)
      changed[0] = (changed[0] & 0x0f) | ((destination & 0x0f) << 4)
      changed[2] = ((destination >> 4) << 5) | 3
      changed_store = bytearray(store)
      changed_store[3] = destination << 1
      for b0 in (0x00, 0x01, 0x40, 0x41, 0x80, 0xc0):
         for b1 in (0x00, 0x04, (destination & 7) << 5):
            main = (bytes((0x1c, 0x00)) + changed + bytes((b0, b1)) +
                    changed_store + stop)
            write(f"dst_{destination:02d}_tail_{b0:02x}{b1:02x}", main)

   # Dense extension fields at the two representative banks.
   for destination, field in ((0, 0), (16, 0x40)):
      changed = bytearray(literal)
      changed[0] = (changed[0] & 0x0f) | ((destination & 0x0f) << 4)
      changed[2] = ((destination >> 4) << 5) | 3
      changed_store = bytearray(store)
      changed_store[3] = destination << 1
      for value in range(256):
         main = (bytes((0x1c, 0x00)) + changed + bytes((value, 0)) +
                 changed_store + stop)
         write(f"dense_dst_{destination:02d}_b0_{value:02x}", main)
         main = (bytes((0x1c, 0x00)) + changed + bytes((field, value)) +
                 changed_store + stop)
         write(f"dense_dst_{destination:02d}_b1_{value:02x}", main)
   print(f"main={base:#x}+{length}")


if __name__ == "__main__":
   main()
