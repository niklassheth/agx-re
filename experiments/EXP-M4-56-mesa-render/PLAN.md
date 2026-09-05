# EXP-M4-56: semantic Mesa vertex and fragment compilation

Target: T8132 M4 mini. Both API shader bodies must be generated from ordinary
NIR through allocated semantic VIR. No complete-shader matching, prescribed
GPR assignments, or copied compiler-inserted algorithms.

Treat historical render encodings as hypotheses. Isolate vertex position/user
exports, fragment coefficient interpolation, and color output using small
explicitly authored shaders. Only inspect operations directly corresponding to
our source; launcher/runtime code stays opaque. Observe package data and call
substitution behavior without reconstructing launcher algorithms.

The existing render package contains a live vertex/fetch program and another
adapter. Prove which program owns positions and varyings by substituting
independently generated arithmetic/outputs and changing them. Do not count an
unchanged Metal vertex program or pixel shape alone as success.

First supported interface: vertex ID, FP32 position and a smooth color varying,
one single-sample unblended RGBA8 attachment. Reuse compute ALU and allocation.
Validate multiple vertex transformations and independent fragment expressions,
including source reuse. Compare covered interior pixels against independent
host geometry/interpolation/arithmetic expectations and background pixels
against the clear value. Retain the compiled binaries and readback evidence.
