# Professional OpenDesk CLI Runner
# Handles virtual environment activation automatically

$scriptPath = Split-Path $MyInvocation.MyCommand.Path -Parent
$venvPath = Join-Path $scriptPath ".venv"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"

if (-Not (Test-Path $pythonExe)) {
    Write-Host " [!] Virtual environment not found at $venvPath" -ForegroundColor Red
    Write-Host " [!] Please run the setup wizard first."
    exit 1
}

# Run the command with the venv python
& $pythonExe "$scriptPath\opendesk\main.py" $args
