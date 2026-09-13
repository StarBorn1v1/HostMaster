"""
models.py — Hostmaster data models

ServerNode, SystemStats, and utility functions for process data.
All psutil calls are wrapped defensively. No bare excepts.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Process name mapping
# ---------------------------------------------------------------------------

PROCESS_NAME_MAP: dict[str, str] = {
    "ollama": "Ollama",
    "node": "Node.js",
    "python": "Python",
    "python3": "Python",
    "uvicorn": "Uvicorn",
    "gunicorn": "Gunicorn",
    "hypercorn": "Hypercorn",
    "daphne": "Daphne",
    "vite": "Vite",
    "next-server": "Next.js",
    "webpack": "Webpack",
    "esbuild": "esbuild",
    "docker": "Docker",
    "dockerd": "Docker",
    "containerd": "containerd",
    "postgres": "PostgreSQL",
    "mysqld": "MySQL",
    "mariadbd": "MariaDB",
    "mongod": "MongoDB",
    "redis-server": "Redis",
    "memcached": "Memcached",
    "nginx": "Nginx",
    "apache2": "Apache",
    "httpd": "Apache",
    "caddy": "Caddy",
    "traefik": "Traefik",
    "haproxy": "HAProxy",
    "code": "VS Code",
    "java": "Java",
    "cargo": "Rust/Cargo",
    "go": "Go",
    "ruby": "Ruby",
    "puma": "Puma",
    "unicorn": "Unicorn",
    "php": "PHP",
    "php-fpm": "PHP-FPM",
    "dotnet": ".NET",
    "celery": "Celery",
    "rabbitmq": "RabbitMQ",
    "beam.smp": "Erlang/OTP",
    "prometheus": "Prometheus",
    "grafana": "Grafana",
    "elasticsearch": "Elasticsearch",
    "kibana": "Kibana",
    "logstash": "Logstash",
    "minio": "MinIO",
    "etcd": "etcd",
    "consul": "Consul",
    "vault": "Vault",
    "ssh": "SSH",
    "sshd": "SSH",
}


def clean_process_name(name: str) -> str:
    """
    Return a human-readable display name for a process name string.

    Matches against PROCESS_NAME_MAP (substring, case-insensitive) first.
    Falls through to capitalizing the first token of the name to strip
    arguments from process strings.
    """
    if not name:
        return "Unknown"
    lower = name.lower()
    for key, display in PROCESS_NAME_MAP.items():
        if key in lower:
            return display
    # Strip any args / path components and capitalize
    return name.split()[0].split("/")[-1].capitalize()


def process_icon_initial(clean_name: str) -> str:
    """Return the first character uppercase — used for avatar letters in the UI."""
    if not clean_name:
        return "?"
    return clean_name[0].upper()


def port_accent_index(port: int) -> int:
    """
    Return a 0-5 index derived from the port number.

    Used in graphics_items to pick from a small palette of six
    neutral-but-distinct accent hues, giving visual variety without
    semantic color-coding.
    """
    return port % 6


# ---------------------------------------------------------------------------
# ServerNode
# ---------------------------------------------------------------------------


@dataclass
class ServerNode:
    """
    Represents a single listening server process bound to a port.

    Fields
    ------
    pid             : OS process ID
    port            : Bound port number
    ip              : Bound IP address string
    process_name    : Raw process name from the OS
    display_label   : Human-facing label shown in the UI
    cmdline         : Full command line string (empty if unavailable)
    clean_name      : Normalized display name (computed in __post_init__)
    """

    pid: int
    port: int
    ip: str
    process_name: str
    display_label: str
    cmdline: str = field(default="")
    cpu_percent: float = field(default=0.0)
    clean_name: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.clean_name = clean_process_name(self.process_name)

    @property
    def identifier(self) -> tuple[int, int]:
        """Unique identifier for this node as (pid, port)."""
        return (self.pid, self.port)

    @property
    def key(self) -> tuple[int, int]:
        """Alias for identifier — kept for backwards compatibility."""
        return self.identifier


# ---------------------------------------------------------------------------
# SystemStats
# ---------------------------------------------------------------------------


@dataclass
class SystemStats:
    """
    Snapshot of host-level system metrics.

    Collected once per refresh cycle and passed down to the sidebar and
    status bar components. All psutil calls are individually guarded.
    """

    hostname: str
    cpu_percent: float
    cpu_cores: int
    cpu_count_physical: int
    ram_used_gb: float
    ram_total_gb: float
    ram_percent: float
    disk_read_mb: float
    disk_write_mb: float
    active_ports_count: int

    @classmethod
    def current(cls, active_ports_count: int = 0) -> "SystemStats":
        """
        Construct a SystemStats snapshot from live psutil readings.

        Every psutil call is individually wrapped so a single failure does
        not prevent the rest of the stats from being collected.
        """
        import psutil  # local import — not a hard dependency at module level

        # Hostname
        try:
            hostname: str = socket.gethostname() or "Local Machine"
        except OSError:
            hostname = "Local Machine"

        # CPU
        try:
            cpu_percent: float = psutil.cpu_percent(interval=None)
        except psutil.Error:
            cpu_percent = 0.0

        try:
            cpu_cores: int = psutil.cpu_count(logical=True) or 1
        except psutil.Error:
            cpu_cores = 1

        try:
            cpu_count_physical: int = psutil.cpu_count(logical=False) or 1
        except psutil.Error:
            cpu_count_physical = 1

        # RAM
        try:
            mem = psutil.virtual_memory()
            ram_used_gb: float = mem.used / (1024 ** 3)
            ram_total_gb: float = mem.total / (1024 ** 3)
            ram_percent: float = mem.percent
        except psutil.Error:
            ram_used_gb = 0.0
            ram_total_gb = 0.0
            ram_percent = 0.0

        # Disk I/O
        try:
            disk_io = psutil.disk_io_counters()
            if disk_io is not None:
                disk_read_mb: float = disk_io.read_bytes / (1024 ** 2)
                disk_write_mb: float = disk_io.write_bytes / (1024 ** 2)
            else:
                disk_read_mb = 0.0
                disk_write_mb = 0.0
        except (psutil.Error, AttributeError, NotImplementedError):
            disk_read_mb = 0.0
            disk_write_mb = 0.0

        return cls(
            hostname=hostname,
            cpu_percent=cpu_percent,
            cpu_cores=cpu_cores,
            cpu_count_physical=cpu_count_physical,
            ram_used_gb=ram_used_gb,
            ram_total_gb=ram_total_gb,
            ram_percent=ram_percent,
            disk_read_mb=disk_read_mb,
            disk_write_mb=disk_write_mb,
            active_ports_count=active_ports_count,
        )
