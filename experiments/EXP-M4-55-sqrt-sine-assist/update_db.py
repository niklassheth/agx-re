#!/usr/bin/env python3
"""Record measured sqrt/sine helpers without altering encoding geometry."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
path = HERE.parents[1]/'tools/agx-isa/db.json'
text = path.read_text()
db = json.loads(text)
desc = next(d for d in db['instructions'] if d['mnemonic']=='fspecial')
fields = {f['name']: f for f in desc['fields']}
fields['fn_hi']['enum']['0'] = 'ordinary family: round / sqrt factor / log2 / sine factor (class-dependent)'
fields['fn_hi']['enum']['1'] = 'reciprocal family: rcp / rsqrt / exp2 (class and operand-form dependent)'
fields['fnclass']['enum']['1'] = '2f: sqrt_factor; af: rsqrt. Equal on positive normals, different at zero/+infinity (EXP-M4-55 T8132)'
fields['fnclass']['enum']['3'] = '2f: sin_factor(x)=sin(pi*x/2)/x on [-1,1], limit pi/2 at zero; NaN outside. af: rsqrt in tested form (EXP-M4-55 T8132)'
note = ('EXP-M4-55 T8132: with ordinary FP32 operand controls, 2f/class1 '
    'returns an rsqrt factor except signed zero, subnormals treated as zero, '
    'and +infinity return 1. A subsequent multiply by x computes fast sqrt; '
    'the factor is not sqrt(x). Negative normals/-infinity/NaN yield NaN. '
    '2f/class3 is an even sine factor sin(pi*x/2)/x for abs(x)<=1, with '
    'limit pi/2 at zero, and NaN for all sampled out-of-domain inputs. It '
    'does not perform argument reduction. Dense/random checks have <=1 ULP '
    'factor error; the composed multiply has <=2 ULP on the measured grid. '
    'These are sampled T8132 results, not exhaustive precision guarantees. ')
fields['fnclass']['note'] = note
sem = desc['semantics']
sem = sem.replace('1 -> rsqrt, 2 -> log2, 3 -> a primitive that returns NaN for 11 of 12 positive-finite inputs (consistent with the sincos/tan range-reduction primitive this enum has always named, not proof of it)',
                  '1 -> sqrt_factor (rsqrt-like on these positive inputs; EXP-M4-55 distinguishes exceptions), 2 -> log2, 3 -> sin_factor (EXP-M4-55 identifies the old unexplained outputs)')
if not sem.startswith('EXP-M4-55'):
    sem = note+sem
desc['semantics'] = sem
start = text.index('  {\n   "mnemonic": "fspecial",')
end = text.index('\n  {\n   "mnemonic":',start+1)
replacement='\n'.join('  '+line for line in json.dumps(desc,indent=1,ensure_ascii=False).splitlines())+',\n'
text = text[:start]+replacement+text[end:]
old = db['length_rule']['byte0_table']['0x2f/0xaf']
new = ('10 [special-function forms: reciprocal, rsqrt, sqrt multiplication '
       'factor, exp2, log2, round, and sine multiplication factor. Function '
       'selection depends on byte0 bit7, byte1 class, and operand controls. '
       'Sqrt/sine factors are identified by EXP-M4-55; neither is a complete '
       'single-op sqrt or full-range sine.]')
text = text.replace(json.dumps(old,ensure_ascii=False),json.dumps(new,ensure_ascii=False))
path.write_text(text)
