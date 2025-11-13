#!/bin/bash
# CCW-MCP Quick Install Script for Linux/macOS

set -e

echo "🚀 CCW-MCP Quick Install Script"
echo "================================"
echo ""

# Check Python version
echo "📋 Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 not found. Please install Python 3.11+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "✅ Python $PYTHON_VERSION found"

# Check uv
echo ""
echo "📋 Checking uv..."
if ! command -v uv &> /dev/null; then
    echo "⚠️  uv not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
else
    UV_VERSION=$(uv --version)
    echo "✅ $UV_VERSION found"
fi

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
uv sync

# Test installation
echo ""
echo "🧪 Testing installation..."
if uv run ccw-mcp --help > /dev/null 2>&1; then
    echo "✅ CCW-MCP installed successfully!"
else
    echo "❌ Error: CCW-MCP failed to start"
    exit 1
fi

# Detect config path
echo ""
echo "📝 Configuration"
if [[ "$OSTYPE" == "darwin"* ]]; then
    CONFIG_DIR="$HOME/Library/Application Support/Claude"
    CONFIG_PATH="$CONFIG_DIR/claude_desktop_config.json"
else
    CONFIG_DIR="$HOME/.config/Claude"
    CONFIG_PATH="$CONFIG_DIR/claude_desktop_config.json"
fi

echo "Config file location: $CONFIG_PATH"

# Create config directory
mkdir -p "$CONFIG_DIR"

# Get absolute path
INSTALL_PATH=$(pwd)

# Generate config
cat > "$CONFIG_PATH" <<EOF
{
  "mcpServers": {
    "ccw-mcp": {
      "command": "uv",
      "args": ["run", "ccw-mcp", "--stdio"],
      "cwd": "$INSTALL_PATH",
      "env": {
        "CCW_STORAGE": "$HOME/.ccw-mcp"
      }
    }
  }
}
EOF

echo "✅ Configuration file created"

echo ""
echo "🎉 Installation complete!"
echo ""
echo "📚 Next steps:"
echo "1. Restart Claude Desktop"
echo "2. Check that ccw-mcp appears in Developer > MCP Servers"
echo "3. Try: 'Create a capsule in /tmp/test'"
echo ""
echo "📖 Documentation:"
echo "- Installation guide: docs/CLAUDE-DESKTOP-INSTALL.md"
echo "- Windows guide: docs/WINDOWS.md"
echo "- Quick start: docs/QUICKSTART-WINDOWS.md"
echo ""
echo "✨ Happy simulating!"
