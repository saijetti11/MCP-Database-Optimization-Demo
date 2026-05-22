# main.py
# Entrypoint — imports tools (registers them) then starts the MCP server.
#
# Usage:
#   python main.py

import tools.db_tools          # registers all 4 @mcp.tool() decorators
from server import mcp

if __name__ == "__main__":
    mcp.run()