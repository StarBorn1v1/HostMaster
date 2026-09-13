"""
scanner.py — Hostmaster background scanner

A non-blocking QThread worker that scans listening network connections via
psutil, computes a diff against cached state, and emits a structured result
signal. All psutil calls are individually guarded. No bare excepts.
"""

from __future__ import annotations

import logging
from typing import Optional

import psutil
from PySide6.QtCore import QThread, Signal

from models import ServerNode, SystemStats, clean_process_name

logger = logging.getLogger(__name__)


class PortScannerWorker(QThread):
    """
    Background QThread that scans all LISTEN-state network connections.

    Emits scan_completed once per run() invocation with a full diff:
      - all_nodes    : every currently-listening ServerNode (sorted by port)
      - added_nodes  : nodes whose (pid, port) key was not in the previous scan
      - removed_keys : (pid, port) tuples present last scan but gone now
      - stats        : SystemStats snapshot collected at scan time
    """

    # Signal signature — must match callers exactly
    scan_completed = Signal(list, list, list, object)
    # (all_nodes: list[ServerNode], added_nodes: list[ServerNode],
    #  removed_keys: list[tuple[int,int]], stats: SystemStats)

    def __init__(self, parent: Optional[object] = None) -> None:
        super().__init__(parent)
        self._cached_keys: set[tuple[int, int]] = set()
        self.revealed_ports: dict[int, tuple[int, str, str]] = {}
        self._running: bool = True

    # ------------------------------------------------------------------
    # Public control
    # ------------------------------------------------------------------

    def stop(self) -> None:
        """Signal the worker to stop after the current scan completes."""
        self._running = False

    # ------------------------------------------------------------------
    # Thread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Scan LISTEN connections, diff against cache, emit results."""
        nodes: list[ServerNode] = []
        seen: set[tuple[int, int]] = set()
        
        if not hasattr(self, '_proc_cache'):
            self._proc_cache: dict[int, tuple[psutil.Process, str, str]] = {}
            
        current_procs = {}

        try:
            connections = psutil.net_connections(kind="inet")
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError, RuntimeError) as e:
            logger.warning("net_connections() failed: %s", e)
            stats = _safe_system_stats(active_ports_count=0)
            self.scan_completed.emit([], [], [], stats)
            return

        for conn in connections:
            if conn.status != "LISTEN" or not conn.laddr:
                continue

            pid: int = conn.pid or 0

            port: int = conn.laddr.port
            ip: str = conn.laddr.ip or "0.0.0.0"

            key: tuple[int, int] = (pid, port)
            
            if pid == 0 and port in self.revealed_ports:
                real_pid, r_name, r_cmd = self.revealed_ports[port]
                key = (real_pid, port)
                if key in seen:
                    continue
                seen.add(key)
                nodes.append(
                    ServerNode(
                        pid=real_pid, port=port, ip=ip,
                        process_name=r_name,
                        display_label=f"{clean_process_name(r_name)} \u2022 {port}",
                        cmdline=r_cmd, cpu_percent=0.0
                    )
                )
                continue

            if key in seen:
                continue
            seen.add(key)

            # --- Process name and CPU (individually guarded) ---
            proc: Optional[psutil.Process] = None
            raw_name: str = "Unknown"
            cmdline: str = ""
            cpu_pct: float = 0.0
            
            try:
                # Reuse cached Process object to get meaningful cpu_percent
                if pid in self._proc_cache:
                    proc, raw_name, cmdline = self._proc_cache[pid]
                    cpu_pct = proc.cpu_percent(interval=None)
                else:
                    proc = psutil.Process(pid)
                    # Initial call returns 0.0 but primes it for next time
                    proc.cpu_percent(interval=None)
                    raw_name = proc.name()
                    cmdline = " ".join(proc.cmdline())
                    
                current_procs[pid] = (proc, raw_name, cmdline)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                raw_name = "Hidden (Requires sudo)" if pid == 0 else "Unknown"
                cmdline = ""

            display_label = f"{clean_process_name(raw_name)} \u2022 {port}"

            nodes.append(
                ServerNode(
                    pid=pid,
                    port=port,
                    ip=ip,
                    process_name=raw_name,
                    display_label=display_label,
                    cmdline=cmdline,
                    cpu_percent=cpu_pct,
                )
            )
            logger.debug("Found LISTEN: pid=%d port=%d name=%s", pid, port, raw_name)

        # Update cache for next run
        self._proc_cache = current_procs

        # Sort by port for consistent ordering before diff computation
        nodes.sort(key=lambda n: n.port)

        # --- Diff against cache ---
        current_keys: set[tuple[int, int]] = {node.key for node in nodes}
        added_nodes: list[ServerNode] = [
            node for node in nodes if node.key not in self._cached_keys
        ]
        removed_keys: list[tuple[int, int]] = list(self._cached_keys - current_keys)

        # Update cached state (only written here — single-threaded per QThread)
        self._cached_keys = current_keys

        logger.debug(
            "Scan complete: total=%d added=%d removed=%d",
            len(nodes),
            len(added_nodes),
            len(removed_keys),
        )

        # --- System stats ---
        stats = _safe_system_stats(active_ports_count=len(nodes))

        self.scan_completed.emit(nodes, added_nodes, removed_keys, stats)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_system_stats(active_ports_count: int) -> SystemStats:
    """
    Return a SystemStats snapshot, falling back to zeroed values if psutil
    raises during collection (e.g. permission error on restricted hosts).
    """
    try:
        return SystemStats.current(active_ports_count=active_ports_count)
    except Exception as e:
        logger.warning("SystemStats.current() failed: %s — using zeroed fallback", e)
        import socket as _socket
        try:
            hostname = _socket.gethostname() or "Local Machine"
        except OSError:
            hostname = "Local Machine"
        return SystemStats(
            hostname=hostname,
            cpu_percent=0.0,
            cpu_cores=1,
            cpu_count_physical=1,
            ram_used_gb=0.0,
            ram_total_gb=0.0,
            ram_percent=0.0,
            disk_read_mb=0.0,
            disk_write_mb=0.0,
            active_ports_count=active_ports_count,
        )
