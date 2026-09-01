#!/usr/bin/env python3

import pathlib
import struct


ROOT = pathlib.Path(__file__).resolve().parent
WORDS = 1024
LANES = 64


def fbits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def input_word(buffer: int, lane: int) -> int:
    if buffer == 0:
        return fbits(((lane % 13) + 1) / 16.0)
    if buffer == 1:
        return fbits(((lane % 11) + 2) / 16.0)
    raise ValueError(buffer)


def as_f32(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def mul_f32(value: float, multiplier: float) -> int:
    return fbits(value * multiplier)


def write(name: str, evaluate) -> None:
    words = [0xCCCCCCCC] * WORDS
    evaluate(words)
    (ROOT / f"{name}.bin").write_bytes(struct.pack(f"<{WORDS}I", *words))


write(
    "alu_xor_alu",
    lambda out: [
        out.__setitem__(
            i,
            ((i * 0x01010101 + 0x10203040) & 0xFFFFFFFF)
            ^ ((i * 0x11111111 + 0x76543210) & 0xFFFFFFFF),
        )
        for i in range(LANES)
    ],
)
write(
    "load_xor_gid",
    lambda out: [
        out.__setitem__(
            i,
            input_word(0, (i * 3 + 1) & 1023)
            ^ ((i * 0x01010101 + 0x10203040) & 0xFFFFFFFF),
        )
        for i in range(LANES)
    ],
)
write(
    "materialized_xor",
    lambda out: [
        out.__setitem__(
            i,
            mul_f32(as_f32(input_word(0, i)), 1.5)
            ^ mul_f32(as_f32(input_word(1, (i + 37) & 1023)), 2.5),
        )
        for i in range(LANES)
    ],
)
write(
    "load_xor_load_distinct",
    lambda out: [
        out.__setitem__(
            i, input_word(0, i) ^ input_word(1, (i + 37) & 1023)
        )
        for i in range(LANES)
    ],
)
write(
    "load_xor_load_same",
    lambda out: [
        out.__setitem__(
            i, input_word(0, i) ^ input_word(0, (i + 37) & 1023)
        )
        for i in range(LANES)
    ],
)


def retain(out: list[int]) -> None:
    for i in range(LANES):
        first = input_word(0, i)
        second = input_word(1, (i + 37) & 1023)
        out[i] = first ^ second
        out[i + 64] = (first + second) & 0xFFFFFFFF


write("load_xor_load_retain", retain)


def chain5(out: list[int]) -> None:
    constants = (0x10203040, 0x21314151, 0x32425262, 0x43536373, 0x54647484)
    for i in range(LANES):
        for value, constant in enumerate(constants):
            loaded = input_word(0, (i + 37 * value) & 1023)
            out[i + 64 * value] = loaded ^ ((i + constant) & 0xFFFFFFFF)


write("load_xor_chain5", chain5)


def chain6(out: list[int]) -> None:
    constants = (
        0x10203040,
        0x21314151,
        0x32425262,
        0x43536373,
        0x54647484,
        0x65758595,
    )
    for i in range(LANES):
        for value, constant in enumerate(constants):
            loaded = input_word(0, (i + 37 * value) & 1023)
            out[i + 64 * value] = loaded ^ ((i + constant) & 0xFFFFFFFF)


write("load_xor_chain6", chain6)
