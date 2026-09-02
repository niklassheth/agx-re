#!/usr/bin/env python3

"""Create fixed-size mode-3 literal ablations from an own-source archive."""

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
   parser.add_argument("--stage", choices=("compute", "vertex", "fragment"),
                       default="compute")
   args = parser.parse_args()

   agxparse = load_agxparse(args.agxparse)
   original = args.archive.read_bytes()
   location = agxparse.locate_region(original, "_agc.main", stage=args.stage)
   if location is None:
      raise SystemExit("_agc.main not found")

   base, length = location
   main_bytes = original[base : base + length]
   literals = []
   for offset in range(len(main_bytes) - 9):
      window = main_bytes[offset : offset + 10]
      if (
         (window[0] & 0x0f) == 0x0c
         and window[1] in (0x80, 0x84)
         and (window[2] & 0x1f) == 3
         and window[8] == 0x40
      ):
         literals.append(offset)

   if not literals:
      raise SystemExit("no mode-3 literals found")

   args.output.mkdir(parents=True, exist_ok=True)
   (args.output / "literal_offsets.txt").write_text(
      "\n".join(f"{offset:#x}" for offset in literals) + "\n"
   )

   variants = {"control": {}}

   # Isolate the two fields on the first literal before applying tuple-wide
   # mutations.  The low five bits of both tail bytes are zero in the corpus.
   first = literals[0]
   for target in range(8):
      variants[f"first_tail_target_{target}"] = {first + 9: target << 5}
   for low in (1, 2, 4, 8, 16):
      variants[f"first_tail_low_{low:02x}"] = {first + 9: low}
   for leader in (0x00, 0x20, 0x40, 0x60, 0x80, 0xc0):
      variants[f"first_tail_leader_{leader:02x}"] = {first + 8: leader}
   for word in (0x0000, 0x000e, 0x550c, 0x551c, 0xffff):
      variants[f"first_tail_word_{word:04x}"] = {
         first + 8: word & 0xff,
         first + 9: word >> 8,
      }

   for mode in range(8):
      variants[f"first_mode_{mode}"] = {
         first + 2: (main_bytes[first + 2] & 0xe0) | mode
      }

   for literal_index, offset in enumerate(literals):
      for value in range(256):
         variants[f"literal_{literal_index}_tail_b0_{value:02x}"] = {
            offset + 8: value
         }
         variants[f"literal_{literal_index}_tail_b1_{value:02x}"] = {
            offset + 9: value
         }
      for target in range(8):
         variants[f"literal_{literal_index}_tail_target_{target}"] = {
            offset + 9: target << 5
         }
      for word in (0x0000, 0x000e, 0x550c, 0x551c, 0xffff):
         variants[f"literal_{literal_index}_tail_word_{word:04x}"] = {
            offset + 8: word & 0xff,
            offset + 9: word >> 8,
         }
      for mode in range(8):
         variants[f"literal_{literal_index}_mode_{mode}"] = {
            offset + 2: (main_bytes[offset + 2] & 0xe0) | mode
         }

   # Mode-only and destination-only mutations retain the exact instruction
   # footprint, allowing the hardware length boundary to reveal itself.
   variants["first_mode2_same_dst"] = {
      first + 2: (main_bytes[first + 2] & 0xe0) | 2
   }
   for word in (0x0000, 0x000e, 0x550c, 0x551c, 0xffff):
      variants[f"first_mode2_tail_word_{word:04x}"] = {
         first + 2: (main_bytes[first + 2] & 0xe0) | 2,
         first + 8: word & 0xff,
         first + 9: word >> 8,
      }
   variants["all_mode2_same_dst"] = {
      offset + 2: (main_bytes[offset + 2] & 0xe0) | 2 for offset in literals
   }

   if len(literals) >= 2:
      second = literals[1]
      variants["both_tail_target_1"] = {first + 9: 0x20, second + 9: 0x20}
      variants["first_tail_1_second_tail_0"] = {first + 9: 0x20}
      variants["first_tail_0_second_tail_1"] = {second + 9: 0x20}

      # Make the two extended destinations collide, and reverse them, without
      # touching the literal payload or tail target.
      variants["second_dst_equals_first"] = {
         second: main_bytes[first],
         second + 2: (main_bytes[second + 2] & 0x1f)
         | (main_bytes[first + 2] & 0xe0),
      }
      variants["swap_extended_dsts"] = {
         first: main_bytes[second],
         first + 2: (main_bytes[first + 2] & 0x1f)
         | (main_bytes[second + 2] & 0xe0),
         second: main_bytes[first],
         second + 2: (main_bytes[second + 2] & 0x1f)
         | (main_bytes[first + 2] & 0xe0),
      }

      # Recode the two literals to direct low-register destinations matching
      # their scalar lane while retaining the two tail words in place.
      variants["both_mode2_direct_r0_r1"] = {
         first: 0x0c,
         first + 2: 0x02,
         second: 0x1c,
         second + 2: 0x02,
      }
      variants["both_mode3_direct_r0_r1"] = {
         first: 0x0c,
         first + 2: 0x03,
         second: 0x1c,
         second + 2: 0x03,
      }

   for name, mutations in variants.items():
      output = bytearray(original)
      for offset, value in mutations.items():
         output[base + offset] = value
      (args.output / f"{name}.bin").write_bytes(output)

   def write_compacted(name, selected):
      compacted = bytearray(main_bytes)
      removed = 0
      for original_offset in selected:
         offset = original_offset - removed
         compacted[offset + 2] = (compacted[offset + 2] & 0xe0) | 2
         del compacted[offset + 8 : offset + 10]
         removed += 2
      compacted.extend(b"\0" * removed)
      if len(compacted) != len(main_bytes):
         raise AssertionError("compacted main changed symbol length")
      output = bytearray(original)
      output[base : base + length] = compacted
      (args.output / f"{name}.bin").write_bytes(output)

   write_compacted("first_mode2_remove_tail", literals[:1])
   write_compacted("all_mode2_remove_tails", literals)

   print(f"main_offset={base:#x} main_length={length} literals={literals}")
   print(f"wrote {len(variants) + 2} variants to {args.output}")


if __name__ == "__main__":
   main()
