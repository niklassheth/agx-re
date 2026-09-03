# SPDX-License-Identifier: MIT
"""Stage, build, and run the own-source T8132 threadgroup-memory matrix."""

import base64
import os
from pathlib import Path
import threading

from m1n1.proxy import EXC_RET


LOCAL_SOURCE = Path(
    "/home/nsheth/Projects/asahi/tmp/agx-re/experiments/"
    "EXP-M4-40-carrier-parameterization/t8132_tgmem_parameter_matrix.m"
)
GUEST_DIR = "/System/Volumes/Data/Users/Shared/g16g-carrier-parameters"
GUEST_TEMP = GUEST_DIR + "/tgmem.m.b64"
GUEST_SOURCE = GUEST_DIR + "/t8132_tgmem_parameter_matrix.m"
GUEST_BINARY = GUEST_DIR + "/t8132_tgmem_parameter_matrix"
GUEST_LOG = GUEST_DIR + "/tgmem-run.log"
GUEST_STATUS = GUEST_DIR + "/tgmem-run.status"

encoded = base64.b64encode(LOCAL_SOURCE.read_bytes()).decode("ascii")
chunks = [encoded[offset:offset + 300] for offset in range(0, len(encoded), 300)]

_original_run_shell = hv.run_shell  # noqa: F821
_state = "waiting"
_chunk_index = 0
_scheduled_interrupt = False
_initial_delay = float(os.environ.get("G16G_TGMEM_STAGE_DELAY", "105"))


def _inject(command):
    written = int(p.hv_vuart_inject(command))  # noqa: F821
    if written != len(command):
        raise RuntimeError(f"short VUART injection: {written}/{len(command)}")


def _schedule_interrupt(delay):
    def worker():
        global _scheduled_interrupt
        _scheduled_interrupt = True
        hv.interrupt()  # noqa: F821

    threading.Timer(delay, worker).start()


def _run_shell(entry_msg="Entering shell", exit_msg="Continuing"):
    global _chunk_index, _scheduled_interrupt, _state

    if entry_msg != "Entering hypervisor shell" or not _scheduled_interrupt:
        return _original_run_shell(entry_msg, exit_msg)
    _scheduled_interrupt = False

    if _state == "waiting":
        _inject((
            "/sbin/mount -P 1; /usr/libexec/init_data_protection; "
            "/sbin/mount -P 2 >/dev/null 2>&1; "
            f"/bin/mkdir -p {GUEST_DIR}; "
            f"rm -f {GUEST_TEMP} {GUEST_LOG} {GUEST_STATUS}; "
            "echo G16G_TGMEM_STAGE_READY\r"
        ).encode("ascii"))
        _state = "chunks"
        _schedule_interrupt(8)
        return EXC_RET.HANDLED

    if _state == "chunks":
        _inject((
            f"printf '%s' '{chunks[_chunk_index]}' >> {GUEST_TEMP}; "
            f"echo G16G_TGMEM_CHUNK={_chunk_index + 1}/{len(chunks)}\r"
        ).encode("ascii"))
        _chunk_index += 1
        if _chunk_index == len(chunks):
            _state = "build"
        _schedule_interrupt(0.75)
        return EXC_RET.HANDLED

    if _state == "build":
        _inject((
            f"/usr/bin/base64 -D < {GUEST_TEMP} > {GUEST_SOURCE}; "
            f"rm -f {GUEST_TEMP}; cd {GUEST_DIR}; "
            f"( /usr/bin/xcrun --sdk macosx clang -arch arm64e -O2 -fobjc-arc "
            "-framework Metal -framework Foundation "
            f"-o {GUEST_BINARY} {GUEST_SOURCE} > {GUEST_LOG} 2>&1 "
            f"&& {GUEST_BINARY} >> {GUEST_LOG} 2>&1; "
            f"echo $? > {GUEST_STATUS}; /bin/sync ) & "
            "echo G16G_TGMEM_BUILD_LAUNCHED; exit\r"
        ).encode("ascii"))
        _state = "report"
        _schedule_interrupt(75)
        return EXC_RET.HANDLED

    if _state == "report":
        _inject((
            f"cd {GUEST_DIR}; echo G16G_TGMEM_REPORT_BEGIN; "
            f"/bin/cat {GUEST_LOG} 2>&1; echo G16G_TGMEM_STATUS; "
            f"/bin/cat {GUEST_STATUS} 2>&1; "
            "echo G16G_TGMEM_REPORT_END\r"
        ).encode("ascii"))
        _state = "finish"
        _schedule_interrupt(15)
        return EXC_RET.HANDLED

    print("T8132 threadgroup-memory matrix staging run complete")
    return EXC_RET.EXIT_GUEST


hv.run_shell = _run_shell  # noqa: F821
_scheduled_interrupt = True
threading.Timer(_initial_delay, hv.interrupt).start()  # noqa: F821
print(
    "T8132 threadgroup-memory staging armed: "
    f"{len(chunks)} chunks after {_initial_delay:.1f}s"
)
