[CmdletBinding()]
param(
    [string]$RepoRoot = (Get-Location).Path,
    [string]$Role,
    [string]$PromptFile,
    [string]$Prompt,
    [string]$OutputFile,
    [string]$MetadataFile,
    [switch]$Json,
    [switch]$NoWrite,
    [int]$TimeoutMs = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$python = if ($env:PYTHON) { $env:PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { $null }
if (-not $python) {
    Write-Host "[FAIL] Python executable not found in PATH."
    exit 1
}

if (-not $Role) {
    Write-Host "[FAIL] -Role is required."
    exit 1
}
if ([string]::IsNullOrWhiteSpace($PromptFile) -and [string]::IsNullOrWhiteSpace($Prompt)) {
    Write-Host "[FAIL] Provide either -PromptFile or -Prompt."
    exit 1
}
if (-not [string]::IsNullOrWhiteSpace($PromptFile) -and -not [string]::IsNullOrWhiteSpace($Prompt)) {
    Write-Host "[FAIL] Provide only one of -PromptFile or -Prompt."
    exit 1
}

$scriptPath = Join-Path $PSScriptRoot "recursive-router-invoke.py"
$argsList = @($scriptPath, "--repo-root", $RepoRoot, "--role", $Role)
if ($PromptFile) { $argsList += @("--prompt-file", $PromptFile) }
if ($Prompt) { $argsList += @("--prompt", $Prompt) }
if ($OutputFile) { $argsList += @("--output-file", $OutputFile) }
if ($MetadataFile) { $argsList += @("--metadata-file", $MetadataFile) }
if ($Json) { $argsList += "--json" }
if ($NoWrite) { $argsList += "--no-write" }
if ($TimeoutMs -gt 0) { $argsList += @("--timeout-ms", $TimeoutMs) }

& $python @argsList
exit $LASTEXITCODE
