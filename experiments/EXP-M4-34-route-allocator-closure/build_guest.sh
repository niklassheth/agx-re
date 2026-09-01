#!/bin/sh
set -eu

parent=../EXP-M4-29-apple9-provenance-matrix
/usr/bin/xcrun --sdk macosx clang -arch arm64e -O2 -fobjc-arc \
  -framework Metal -framework Foundation \
  -o native_runner "$parent/native_runner.m"

echo "built EXP-M4-34 native runner"
