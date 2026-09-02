#!/usr/bin/env python3

"""Place mode-2/mode-3 raw literals before the same ordinary device store."""

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
   parser.add_argument("carrier", type=Path)
   parser.add_argument("literal_store", type=Path)
   parser.add_argument("agxparse", type=Path)
   parser.add_argument("output", type=Path)
   args = parser.parse_args()
   agxparse = load_agxparse(args.agxparse)

   carrier = args.carrier.read_bytes()
   carrier_base, carrier_length = agxparse.locate_region(
      carrier, "_agc.main", stage="compute")
   reference = args.literal_store.read_bytes()
   ref_base, ref_length = agxparse.locate_region(
      reference, "_agc.main", stage="compute")
   ref = reference[ref_base : ref_base + ref_length]

   # Native literal_store is: get_sr(4), raw literal(8), store(14), stop(4).
   prefix = ref[:4]
   literal = bytearray(ref[4:12])
   store_and_stop = ref[12:30]
   if len(prefix) != 4 or len(literal) != 8 or len(store_and_stop) != 18:
      raise SystemExit("unexpected literal_store layout")

   args.output.mkdir(parents=True, exist_ok=True)

   def write(name, body):
      if len(body) > carrier_length:
         raise ValueError("program exceeds carrier main")
      code = body + bytes(carrier_length - len(body))
      output = bytearray(carrier)
      output[carrier_base : carrier_base + carrier_length] = code
      (args.output / f"{name}.bin").write_bytes(output)

   write("native_mode2", prefix + literal + store_and_stop)
   for destination in (0, 2, 3, 8, 15, 16, 18, 19, 24, 31, 32, 63):
      changed = bytearray(literal)
      changed[0] = (changed[0] & 0x0f) | ((destination & 0x0f) << 4)
      changed[2] = ((destination >> 4) << 5) | 2
      changed_tail = bytearray(store_and_stop)
      changed_tail[3] = destination << 1
      write(f"mode2_dst_{destination:02d}",
            prefix + changed + changed_tail)
   for mode in range(8):
      changed = bytearray(literal)
      changed[2] = (changed[2] & 0xe0) | mode
      for b0, b1 in ((0x40, 0x00), (0x40, 0x04), (0x40, 0x60),
                     (0xc0, 0x00), (0x20, 0x00)):
         write(f"mode_{mode}_tail_{b0:02x}{b1:02x}",
               prefix + changed + bytes((b0, b1)) + store_and_stop)

   print(f"carrier={carrier_base:#x}+{carrier_length} ref={ref_base:#x}+{ref_length}")


if __name__ == "__main__":
   main()
