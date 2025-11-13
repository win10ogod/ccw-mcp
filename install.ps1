# CCW-MCP Quick Install Script for Windows
# Run with: powershell -ExecutionPolicy Bypass -File install.ps1

Write-Host "🚀 CCW-MCP Quick Install Script" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Check Python version
Write-Host "📋 Checking Python version..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ $pythonVersion found" -ForegroundColor Green
} catch {
    Write-Host "❌ Error: Python not found. Please install Python 3.11+" -ForegroundColor Red
    Write-Host "Download from: https://python.org" -ForegroundColor Yellow
    exit 1
}

# Check uv
Write-Host ""
Write-Host "📋 Checking uv..." -ForegroundColor Yellow
try {
    $uvVersion = uv --version 2>&1
    Write-Host "✅ $uvVersion found" -ForegroundColor Green
} catch {
    Write-Host "⚠️  uv not found. Installing..." -ForegroundColor Yellow
    irm https://astral.sh/uv/install.ps1 | iex
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","User")
}

# Install dependencies
Write-Host ""
Write-Host "📦 Installing dependencies..." -ForegroundColor Yellow
uv sync

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Error: Failed to install dependencies" -ForegroundColor Red
    exit 1
}

# Test installation
Write-Host ""
Write-Host "🧪 Testing installation..." -ForegroundColor Yellow
$testOutput = uv run ccw-mcp --help 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ CCW-MCP installed successfully!" -ForegroundColor Green
} else {
    Write-Host "❌ Error: CCW-MCP failed to start" -ForegroundColor Red
    exit 1
}

# Configuration
Write-Host ""
Write-Host "📝 Configuration" -ForegroundColor Yellow

$configDir = "$env:APPDATA\Claude"
$configPath = "$configDir\claude_desktop_config.json"

Write-Host "Config file location: $configPath" -ForegroundColor Cyan

# Create config directory
New-Item -ItemType Directory -Force -Path $configDir | Out-Null

# Get absolute path (with escaped backslashes)
$installPath = (Get-Location).Path -replace '\\', '\\'

# Generate config
$config = @"
{
  "mcpServers": {
    "ccw-mcp": {
      "command": "uv",
      "args": ["run", "ccw-mcp", "--stdio"],
      "cwd": "$installPath",
      "env": {
        "CCW_STORAGE": "$env:USERPROFILE\\.ccw-mcp"
      }
    }
  }
}
"@

$config | Out-File -FilePath $configPath -Encoding UTF8

Write-Host "✅ Configuration file created" -ForegroundColor Green

Write-Host ""
Write-Host "🎉 Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📚 Next steps:" -ForegroundColor Cyan
Write-Host "1. Restart Claude Desktop" -ForegroundColor White
Write-Host "2. Check that ccw-mcp appears in Developer > MCP Servers" -ForegroundColor White
Write-Host "3. Try: 'Create a capsule in C:\temp\test'" -ForegroundColor White
Write-Host ""
Write-Host "📖 Documentation:" -ForegroundColor Cyan
Write-Host "- Installation guide: docs\CLAUDE-DESKTOP-INSTALL.md" -ForegroundColor White
Write-Host "- Windows guide: docs\WINDOWS.md" -ForegroundColor White
Write-Host "- Quick start: docs\QUICKSTART-WINDOWS.md" -ForegroundColor White
Write-Host ""
Write-Host "✨ Happy simulating!" -ForegroundColor Magenta
