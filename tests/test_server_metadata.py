from importlib.metadata import version

from ida_pro_mcp.server_metadata import (
    DISTRIBUTION_NAME,
    MCP_PACKAGE_VERSION,
    MCP_SERVER_INSTRUCTIONS,
)


def test_mcp_package_version_matches_installed_distribution():
    assert MCP_PACKAGE_VERSION == version(DISTRIBUTION_NAME)


def test_mcp_server_instructions_are_self_contained_and_bounded():
    assert len(MCP_SERVER_INSTRUCTIONS) == 337
    for required_fragment in (
        "Absolute paths",
        "force_headless",
        "idb_open_status",
        "indeterminate",
        "idb_cancel_open",
        "database=session_id",
        "analysis_barrier",
        "server_health(status=ok,ready=true)",
        "Respect profile",
        "idb_close",
    ):
        assert required_fragment in MCP_SERVER_INSTRUCTIONS
