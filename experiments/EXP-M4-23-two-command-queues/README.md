# EXP-M4-23: two Metal command queues on one G16 device

Clean-room public-Metal experiment. One `MTLDevice` creates two distinct
`MTLCommandQueue` objects. Both queues share one caller-created pipeline and
one output buffer, alternate three completed submissions (`q0`, `q1`, `q0`),
then commit one submission from each queue before either is waited.

The harness is `tools/iotrace/iohello_compute_two_queues.m`. Runtime traces
and per-stage caller-BO snapshots are stored under `work/`.
