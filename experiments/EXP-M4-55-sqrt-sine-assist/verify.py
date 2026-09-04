#!/usr/bin/env python3
"""Check the pre-recorded helper hypotheses against raw hardware results."""
import json
import math
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
rows = json.loads((HERE/'HARDWARE.json').read_text())

def f32(u):
    return struct.unpack('<f', struct.pack('<I', u))[0]

def bits(x):
    return struct.unpack('<I', struct.pack('<f', x))[0]

def daz(x):
    return math.copysign(0, x) if abs(x) < 2**-126 else x

def rsqrt(x, sqrt_factor=False):
    x = daz(x)
    if sqrt_factor and (x == 0 or x == math.inf):
        return 1.
    if x < 0 or math.isnan(x):
        return math.nan
    return math.copysign(math.inf, x) if x == 0 else 1/math.sqrt(x)

def sinc(x):
    if not math.isfinite(x) or abs(x) > 1:
        return math.nan
    return math.sin(math.pi/2*x)/x if x else math.pi/2

reports = []
failures = []
checked = 0
for row in rows:
    name, tag = row['name'], row['tag']
    # These native outputs establish compiler context, not an accuracy claim
    # about Metal's complete range reduction at infinities/large arguments.
    if tag == 'native_edges' and name in ['k_sin','k_sin_fast','k_sinpi','k_cospi']:
        reports.append(dict(name=name, tag=tag, role='native-context-only'))
        continue
    worst = 0
    for i, (a,b) in enumerate(zip(row['inputs'], row['outputs'])):
        x, got = f32(int(a,16)), f32(int(b,16))
        if tag.startswith('sine_factor_multiply'):
            expected = math.sin(math.pi/2*daz(x)) if math.isfinite(x) and abs(x)<=1 else math.nan
        elif tag == 'ordinary_rsqrt_multiply_edges':
            expected = daz(x)*f32(bits(rsqrt(x)))
        elif tag.startswith('class3') and not tag.startswith('class3_af'):
            expected = sinc(x)
        elif name in ['k_sqrt','k_sqrt_precise']:
            expected = math.sqrt(daz(x)) if not x < 0 or abs(x)<2**-126 else math.nan
        else:
            expected = rsqrt(x, tag.startswith('root_2f') or tag.startswith('sqrt_factor'))
        if math.isnan(expected):
            good = math.isnan(got)
        elif not math.isfinite(expected) or expected == 0:
            good = bits(got) == bits(expected)
        else:
            error = abs(int(b,16)-bits(expected))
            worst = max(worst, error)
            good = math.isfinite(got) and error <= 2
        checked += 1
        if not good:
            failures.append(dict(name=name, tag=tag, lane=i, input=a, output=b, expected=expected))
    reports.append(dict(name=name, tag=tag, count=len(row['inputs']), max_ulp=worst))

by_tag = {r['tag']: r for r in rows}
a, b = by_tag['root_af_random'], by_tag['root_2f_random']
assert a['inputs'] == b['inputs']
factor_mismatches = sum(x!=y for x,y in zip(a['outputs'], b['outputs']))
for forward, backward in [('class3_dense','class3_dense_reverse'),
                          ('root_2f_b0','sqrt_factor_edges_reverse')]:
    assert by_tag[forward]['outputs'] == list(reversed(by_tag[backward]['outputs']))
result = dict(dispatches=len(rows), numerical_checks=checked,
              positive_normal_root_factor_bit_mismatches=factor_mismatches,
              reports=reports, failures=failures,
              verdict='PASS' if not failures and not factor_mismatches else 'FAIL')
(HERE/'VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
raise SystemExit(bool(failures or factor_mismatches))
