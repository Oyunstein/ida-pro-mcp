"""Shared MCP handshake identity and cross-tool guidance."""

from importlib.metadata import PackageNotFoundError, version


DISTRIBUTION_NAME = "ida-pro-mcp"


def _installed_package_version() -> str:
    try:
        return version(DISTRIBUTION_NAME)
    except PackageNotFoundError:
        return "0+unknown"


MCP_PACKAGE_VERSION = _installed_package_version()
MCP_SERVER_INSTRUCTIONS = (
    "Absolute paths; forwarded tools need database=session_id. Open force_headless; "
    "poll idb_open_status. Timeouts are indeterminate: re-query; never "
    "duplicate/restart pending work. Cancel only via idb_cancel_open. Gate "
    "first/final analysis with analysis_barrier then "
    "server_health(status=ok,ready=true). Respect profile; close via idb_close."
)
