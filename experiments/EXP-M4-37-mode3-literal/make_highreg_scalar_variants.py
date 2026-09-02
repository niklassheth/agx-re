#!/usr/bin/env python3

"""Separate high-GPR MOV_IMM32 writes from device-store source selection.

The old destination cross changed both the MOV_IMM32 destination and the
source descriptor of a following published device store.  These variants put
an ordinary IADD between those operations and always store the IADD's implicit
low-register result.  A second family seeds the same high GPR with IADD, so a
failure can be assigned to MOV_IMM32 rather than the IADD source encoding.
"""

import argparse
import importlib.util
from pathlib import Path


VALUE = 0x12345678
FLOAT_ONE = 0x3F800000
DESTINATIONS = (2, 15, 16, 18, 19, 24, 31, 32, 63)


def load_agxparse(path):
   spec = importlib.util.spec_from_file_location("agxparse", path)
   module = importlib.util.module_from_spec(spec)
   spec.loader.exec_module(module)
   return module


def set_bits(blob, start, width, value):
   if value >= (1 << width):
      raise ValueError((start, width, value))
   for bit in range(width):
      absolute = start + bit
      mask = 1 << (absolute & 7)
      if value & (1 << bit):
         blob[absolute >> 3] |= mask
      else:
         blob[absolute >> 3] &= ~mask


def mov_imm(dst, value):
   if dst >= 16 or value > 0x7f:
      raise ValueError((dst, value))
   return bytes(((dst << 4) | 0x0c, value))


def mov_imm32(dst, value, state=0):
   if dst >= 16 or state >= 8:
      raise ValueError((dst, state))
   return bytes((
      (dst << 4) | 0x0c,
      0x80 | (value & 0x7f),
      (state << 5) | 0x02,
      (value >> 24) & 0xfe,
      (value >> 6) & 0x1e,
      (value >> 9) & 0x0c,
      (value >> 13) & 0xff,
      (value >> 21) & 0x0f,
   ))


def literal_pair(dst, value, second_leader_nibble):
   """Emit the observed 2-byte prefix plus 6-byte low-nibble-2 record.

   This deliberately does not assume that the eight bytes are one instruction.
   The high nibble of byte 2 is swept independently below.
   """
   if dst >= 16 or second_leader_nibble >= 16:
      raise ValueError((dst, second_leader_nibble))
   return bytes((
      (dst << 4) | 0x0c,
      0x80 | (value & 0x7f),
      (second_leader_nibble << 4) | 0x02,
      (value >> 24) & 0xfe,
      (value >> 6) & 0x1e,
      (value >> 9) & 0x0c,
      (value >> 13) & 0xff,
      (value >> 21) & 0x0f,
   ))


def mov_imm32_old_extended_hypothesis(dst, value):
   """Encode the disproven byte-2 destination-extension hypothesis."""
   return mov_imm32(dst & 0x0f, value, dst >> 4)


def iadd(dst, src0, src1):
   # Hardware-validated all-sources-last-use form used by Mesa's Apple9 packer.
   instruction = bytearray((
      0x9f, 0x01, 0x56, 0x00, 0x02,
      0x00, 0x00, 0xa8, 0x17, 0x05,
   ))
   set_bits(instruction, 25, 7, dst)
   set_bits(instruction, 42, 7, src0)
   set_bits(instruction, 51, 7, src1)
   return bytes(instruction)


def fadd(dst, src0, src1, route):
   instruction = bytearray((0x09, 0x05, 0x1c, 0x01, 0x00, 0x00))
   set_bits(instruction, 21, 1, 1)
   set_bits(instruction, 45, 3, route)
   set_bits(instruction, 4, 4, dst)
   set_bits(instruction, 9, 6, src0)
   set_bits(instruction, 25, 6, src1)
   return bytes(instruction)


def store_implicit_alu(data, index, binding):
   # The immediately preceding ALU result is consumed implicitly.  The data
   # descriptor remains accurate but is deliberately always r0 here.
   instruction = bytearray((
      0xe7, 0x00, 0x54, 0x00, 0x00, 0x00, 0x21,
      0x00, 0x11, 0x00, 0x00, 0x10, 0x11, 0x00,
   ))
   instruction[3] = data << 1
   instruction[4] = binding
   instruction[5] = index
   return bytes(instruction)


def store_published_gpr(data, index, binding):
   instruction = bytearray(store_implicit_alu(data, index, binding))
   instruction[1] = 0x10
   return bytes(instruction)


def stop():
   return bytes((0x0e, 0x00, 0x00, 0x00))


def main():
   parser = argparse.ArgumentParser()
   parser.add_argument("carrier", type=Path)
   parser.add_argument("agxparse", type=Path)
   parser.add_argument("output", type=Path)
   args = parser.parse_args()

   agxparse = load_agxparse(args.agxparse)
   original = args.carrier.read_bytes()
   base, length = agxparse.locate_region(
      original, "_agc.main", stage="compute")
   args.output.mkdir(parents=True, exist_ok=True)

   def write(name, program):
      if len(program) > length:
         raise ValueError((name, len(program), length))
      archive = bytearray(original)
      archive[base : base + length] = program + bytes(length - len(program))
      (args.output / f"{name}.bin").write_bytes(archive)
      (args.output / f"{name}.hex").write_text(program.hex() + "\n")

   # r1 is both the zero addend and output index.  Releasing it through IADD is
   # harmless because the required index remains zero.
   for destination in DESTINATIONS:
      program = (
         mov_imm(1, 0) +
         mov_imm32_old_extended_hypothesis(destination, VALUE) +
         iadd(0, destination, 1) +
         store_implicit_alu(0, 1, 1) +
         stop()
      )
      write(f"imm32_r{destination:02d}_via_iadd", program)

      # Control the consumer's ability to read the same register independently
      # of MOV_IMM32: synthesize 7 in that register with an ordinary IADD.
      program = (
         mov_imm(1, 0) +
         mov_imm(2, 7) +
         iadd(destination, 2, 1) +
         iadd(0, destination, 1) +
         store_implicit_alu(0, 1, 1) +
         stop()
      )
      write(f"iadd_r{destination:02d}_via_iadd", program)

      if destination >= 16:
         # Test whether byte 2's high bits extend the destination at all.  The
         # record is unchanged; only the following IADD reads the low-nibble
         # register named by byte 0 instead of the hypothesized extended one.
         program = (
            mov_imm(1, 0) +
            mov_imm32_old_extended_hypothesis(destination, VALUE) +
            iadd(0, destination & 0x0f, 1) +
            store_implicit_alu(0, 1, 1) +
            stop()
         )
         write(
            f"imm32_encoded_r{destination:02d}_read_r{destination & 0x0f:02d}",
            program,
         )

         # Reproduce the original direct-store shape, but make the store read
         # the byte-0 low-nibble destination instead of treating byte 2 as a
         # destination extension.
         program = (
            mov_imm(1, 0) +
            mov_imm32_old_extended_hypothesis(destination, VALUE) +
            store_published_gpr(destination & 0x0f, 1, 1) +
            stop()
         )
         write(
            f"imm32_encoded_r{destination:02d}_store_r{destination & 0x0f:02d}",
            program,
         )

   # Hold the actual low-nibble destination and consumer fixed while sweeping
   # all three high bits of byte 2.  This directly tests whether they are a
   # register extension or orthogonal execution/lifetime state.
   for high in range(8):
      program = (
         mov_imm(1, 0) +
         mov_imm32(2, VALUE, high) +
         iadd(0, 2, 1) +
         store_implicit_alu(0, 1, 1) +
         stop()
      )
      write(f"imm32_b2hi_{high}_read_r02", program)

      # Cross the complete byte-2 state with FALU's independently recovered
      # three-bit pending-result route, in both operand roles.  If byte-2 state
      # allocates a scoreboard slot, this exposes its route mapping directly.
      for route in range(8):
         for role in ("a", "b"):
            src0, src1 = (2, 1) if role == "a" else (1, 2)
            program = (
               mov_imm(1, 0) +
               mov_imm32(2, FLOAT_ONE, high) +
               fadd(0, src0, src1, route) +
               store_implicit_alu(0, 1, 1) +
               stop()
            )
            write(f"imm32_state_{high}_fadd_{role}_route_{route}", program)

   # Treat byte 2 as the leader of the following six-byte low-nibble-2
   # record and sweep its complete high nibble.  Read every compact GPR after
   # the pair so a relocated result cannot masquerade as a suppressed write.
   for leader_nibble in range(16):
      for source in range(16):
         zero = 1 if source != 1 else 15
         program = (
            mov_imm(zero, 0) +
            literal_pair(2, VALUE, leader_nibble) +
            iadd(0, source, zero) +
            store_implicit_alu(0, zero, 1) +
            stop()
         )
         write(
            f"literal_pair_leader_{leader_nibble:x}_read_r{source:02d}",
            program,
         )

      # Distinguish a suppressed write from an explicit zero result.
      program = (
         mov_imm(1, 0) +
         mov_imm(2, 7) +
         literal_pair(2, VALUE, leader_nibble) +
         iadd(0, 2, 1) +
         store_implicit_alu(0, 1, 1) +
         stop()
      )
      write(f"literal_pair_leader_{leader_nibble:x}_preseed_r02", program)

   # The corpus uses even leader nibbles 4..c almost exclusively in very
   # high-pressure ray-query programs.  Probe both natural bank ladders rather
   # than assuming those forms suppress the result outright.
   for leader_nibble in range(16):
      candidates = {
         2,
         leader_nibble,
         (leader_nibble >> 2) * 16 + 2,
         leader_nibble * 8 + 2,
         max(0, leader_nibble - 2) * 8 + 2,
      }
      for source in sorted(r for r in candidates if r < 96):
         program = (
            mov_imm(1, 0) +
            literal_pair(2, VALUE, leader_nibble) +
            iadd(0, source, 1) +
            store_implicit_alu(0, 1, 1) +
            stop()
         )
         write(
            f"literal_pair_bank_{leader_nibble:x}_read_r{source:02d}",
            program,
         )

   # Cross the recovered bank selector with several low destination nibbles.
   # The predicted full destination is low + 16 * (leader_nibble >> 2).
   for leader_nibble in range(16):
      for low in (0, 2, 15):
         source = low + 16 * (leader_nibble >> 2)
         program = (
            mov_imm(1, 0) +
            literal_pair(low, VALUE, leader_nibble) +
            iadd(0, source, 1) +
            store_implicit_alu(0, 1, 1) +
            stop()
         )
         write(
            f"literal_pair_fullmap_{leader_nibble:x}_low_{low:02d}_read_r{source:02d}",
            program,
         )

   print(f"main={base:#x}+{length}")


if __name__ == "__main__":
   main()
