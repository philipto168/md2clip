# Install md2clip - Markdown clipboard converter
# Run this once to set up the tool

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Installing md2clip..." -ForegroundColor Cyan

# Create venv
if (-not (Test-Path "$scriptDir\.venv")) {
    python -m venv "$scriptDir\.venv"
}

# Install dependencies
& "$scriptDir\.venv\Scripts\python.exe" -m pip install -r "$scriptDir\requirements.txt" --quiet

# Create a batch wrapper so you can just type 'md2clip' from anywhere
$batchContent = @"
@echo off
"$scriptDir\.venv\Scripts\python.exe" "$scriptDir\md2clip.py" %*
"@
Set-Content -Path "$scriptDir\md2clip.bat" -Value $batchContent

# Add to PATH if not already there
$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -notlike "*$scriptDir*") {
    [Environment]::SetEnvironmentVariable("PATH", "$userPath;$scriptDir", "User")
    Write-Host "Added $scriptDir to user PATH." -ForegroundColor Green
    Write-Host "Restart your terminal for PATH changes to take effect." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done! Usage:" -ForegroundColor Green
Write-Host "  md2clip        # Convert clipboard markdown to rich text (one-shot)"
Write-Host "  md2clip --tray # Run as system tray icon"
Write-Host ""
