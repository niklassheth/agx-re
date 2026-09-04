#!/usr/bin/env python3
"""Independent composition checks after isolating the two helper functions."""
import json
import probe as p

p.records = json.loads((p.HERE/'HARDWARE.json').read_text())
by_tag = {r['tag']: r for r in p.records}
edges = [int(x,16) for x in by_tag['root_2f_b0']['inputs']]
dense = [int(x,16) for x in by_tag['class3_dense']['inputs']]
# Keep native sqrt's allocated source, factor result, and ordinary multiply.
# Alter only function selection; never use a proprietary helper program.
p.execute('k_sqrt', 'ordinary_rsqrt_multiply_edges', edges,
          'af015604030092400000')
p.execute('k_sqrt', 'sine_factor_multiply_edges', edges,
          '2f035604030092400000')
p.execute('k_sqrt', 'sine_factor_multiply_dense', dense,
          '2f035604030092400000')
# Reverse the lane order to check that domain classification is per-input.
p.execute('k_rsqrt', 'class3_dense_reverse', list(reversed(dense)),
          '2f0356000200b0400000')
p.execute('k_rsqrt', 'sqrt_factor_edges_reverse', list(reversed(edges)),
          '2f0156000200b0400000')
