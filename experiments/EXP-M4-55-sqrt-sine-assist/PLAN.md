# Sqrt and sine-assist semantics: initial predictions

Own-source Metal and hardware mutations only. Inspect/mutate `_agc.main` only.

The old class-3 raw output at x=0.25, 0.5, 0.125 is respectively 1.5307337,
1.41421354, 1.56072259. Before new execution, these fit
`sin(pi*x/2)/x`, with limit pi/2 at zero. Test both signs, zero, dense samples,
domain boundaries, and values beyond [-1,1]. Distinguish this from sin, cos,
asin, and a remainder/quadrant computation. NaNs are classified explicitly.

Native fast sqrt consists of class-1 `2f` followed by a multiply. Hypothesis:
the first instruction computes a reciprocal-root factor, possibly with special
zero/infinity handling different from `af` class 1. Compare both families on
identical inputs, capture the intermediate, then validate final multiplication.

Use the same native rsqrt carrier for isolated generated instructions and keep
source/destination/dependency controls fixed. Separate instruction semantics
from the surrounding Metal range reduction; do not copy its lowering algorithm
or polynomial coefficients into Mesa.
