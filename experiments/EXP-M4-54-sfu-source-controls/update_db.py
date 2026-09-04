#!/usr/bin/env python3
"""Correct descriptive SFU metadata, without changing match/encoding geometry."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
path = HERE.parents[1]/'tools/agx-isa/db.json'
text = path.read_text()
db = json.loads(text)
desc = next(x for x in db['instructions'] if x['mnemonic'] == 'fspecial')
fields = {f['name']: f for f in desc['fields']}
release = ('Source release is controlled independently by byte+6 bit 4 for '
           'reciprocal, but bit 5 for ordinary SFU (EXP-M4-54, T8132).')
fields['src']['note'] = fields['src']['note'].replace(
    'Source release is controlled independently by byte+6 bit 4.', release)
fields['fnsel']['enum'].update({
    '176': 'ordinary SFU FP32 source, released (0x90 | 0x20)',
    '144': 'ordinary SFU FP32 source, retained',
    '160': 'ordinary SFU BF16 source, released (0x80 | 0x20)',
    '128': 'ordinary SFU BF16 source, retained',
    '168': 'ordinary SFU FP16 source / FP32 result form, released',
    '136': 'ordinary SFU FP16 source / FP32 result form, retained',
    '172': 'ordinary SFU FP16 source / FP16 result form, released',
    '140': 'ordinary SFU FP16 source / FP16 result form, retained',
    '146': 'ordinary SFU FP32 retained-source form with bit1 set; bit1 not characterized',
    '2': 'reciprocal retained-source variant; bit1 did not change tested result/lifetime',
})
fields['fnsel']['note'] = (
    'Historical name: this byte combines form-specific operand controls, not '
    'just function selection. EXP-M4-54 matched native captures and destructive '
    'reuse mutations prove reciprocal release bit4, ordinary-SFU release bit5 '
    'for FP32 and FP16. Ordinary-SFU source type is bits[4:3]: 0=BF16, 1=FP16, '
    '2=FP32 in measured forms. Changing 0xb0 to 0xa0 selects low BF16 input; '
    'it does not retain FP32. Reciprocal uses byte7 bits[3:2] for these types '
    'instead. Pending dependency bits12..17 are independent. Narrow source '
    'and result register addressing is not generalized by this metadata update.')
fields['precsel']['enum'].update({
    '72': 'reciprocal FP32 source / FP32 result form',
    '68': 'reciprocal FP16 source / FP32 result form',
    '192': 'ordinary SFU FP32 result with source absolute-value modifier',
})
fields['precsel']['note'] = (
    'EXP-M4-54 T8132: ordinary-SFU bit7 applies source absolute value; '
    'reciprocal source absolute value instead uses byte8 bit6. Reciprocal '
    'FP32-result source types use byte7 0x40/0x44/0x48 for BF16/FP16/FP32. '
    'Other result-width controls remain form-specific.')
fields['roundmode']['enum']['1'] = 'ordinary-SFU source negation (not a universal NaN control)'
fields['roundmode']['note'] = (
    'EXP-M4-54 T8132: bit0 negates the ordinary-SFU source. Native negated '
    'rsqrt/exp2/log2/floor and mixed-sign mutations prove the arithmetic. '
    'The earlier positive-only G17P rsqrt/log2 probes returned NaN because '
    'negation made their inputs negative; the universal do-not-emit inference '
    'is withdrawn. Direct-round bits[2:1] retain the rounding selection. '
    'Reciprocal has a distinct layout: byte8 bit6 is source absolute value.')
sem = desc['semantics']
sem = sem.replace('Source release is controlled independently by byte+6 bit 4 (EXP-M4-41).', release)
a = sem.index('ROUND MODE / NaN BIT ')
b = sem.index('OTHER FIELDS,', a)
sem = sem[:a] + fields['roundmode']['note'] + ' ' + sem[b:]
sem = sem.replace('the flag now marks the two documented do-not-emit regions, byte+3 >= 192 and byte+8 bit 0.',
    'the flag conservatively retains the invalid destination boundary byte+3 >= 192 and incompletely modeled operand forms; byte+8 bit0 is legal source negation on the ordinary SFU.')
desc['semantics'] = ('EXP-M4-54 T8132 CORRECTION: reciprocal and ordinary SFU '
    'have different operand-control layouts. ' + fields['fnsel']['note'] + ' ' + sem)
# Replace only this descriptor; preserve all other database formatting/edits.
start = text.index('  {\n   "mnemonic": "fspecial",')
end = text.index('\n  {\n   "mnemonic":', start+1)
replacement = '\n'.join('  '+line for line in json.dumps(desc, indent=1, ensure_ascii=False).splitlines())+',\n'
path.write_text(text[:start]+replacement+text[end:])
