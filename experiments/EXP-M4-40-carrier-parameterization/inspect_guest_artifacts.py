# SPDX-License-Identifier: MIT
"""Locate prior own-source Metal compute artifacts in the T8132 guest."""

import os
import threading

from m1n1.proxy import EXC_RET


_original_run_shell = hv.run_shell  # noqa: F821
_state = "waiting"
_inspect_due = False
_scheduled_interrupt = False
_delay = float(os.environ.get("G16G_INSPECT_DELAY", "105"))


def _request_inspect():
    global _inspect_due
    _inspect_due = True
    hv.interrupt()  # noqa: F821


def _schedule_interrupt(delay):
    def worker():
        global _scheduled_interrupt
        _scheduled_interrupt = True
        hv.interrupt()  # noqa: F821

    threading.Timer(delay, worker).start()


def _run_shell(entry_msg="Entering shell", exit_msg="Continuing"):
    global _state

    if (
        _state == "waiting"
        and _inspect_due
        and entry_msg == "Entering hypervisor shell"
    ):
        command = (
            "/sbin/mount -P 1; /usr/libexec/init_data_protection; "
            "/sbin/mount -P 2 >/dev/null 2>&1; "
            "echo G16G_ARTIFACT_SEARCH_BEGIN; "
            "/usr/bin/find /System/Volumes/Data/Users -maxdepth 6 "
            "\\( -iname '*sync*cfg*' -o -iname '*shared*exchange*' "
            "-o -iname '*shared*phase*' -o -iname '*compute*matrix*' "
            "-o -iname '*tgmem*' \\) -print 2>/dev/null | /usr/bin/head -n 300; "
            "echo G16G_SHARED_DIR; /bin/ls -la /System/Volumes/Data/Users/Shared 2>&1; "
            "echo G16G_ARTIFACT_SEARCH_END\r"
        ).encode("ascii")
        written = int(p.hv_vuart_inject(command))  # noqa: F821
        if written != len(command):
            raise RuntimeError(f"short VUART injection: {written}/{len(command)}")
        _state = "inspect"
        _schedule_interrupt(30)
        return EXC_RET.HANDLED

    if (
        _state == "inspect"
        and _scheduled_interrupt
        and entry_msg == "Entering hypervisor shell"
    ):
        print("T8132 guest artifact inspection complete")
        return EXC_RET.EXIT_GUEST

    return _original_run_shell(entry_msg, exit_msg)


hv.run_shell = _run_shell  # noqa: F821
threading.Timer(_delay, _request_inspect).start()
print(f"T8132 guest artifact inspection armed after {_delay:.1f}s")
