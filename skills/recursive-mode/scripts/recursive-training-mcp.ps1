#Requires -Version 5.1
<#
.SYNOPSIS
    MCP server for repository experiences (PowerShell wrapper).

.DESCRIPTION
    Thin wrapper that calls recursive-training-mcp.py with the same arguments.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot
)

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python3 -ErrorAction SilentlyContinue
}

if (-not $python) {
    Write-Error "Python is required but not found. Please install Python 3.10+."
    exit 1
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyScript = Join-Path $scriptDir "recursive-training-mcp.py"

& $python.Source $pyScript @("--repo-root", $RepoRoot)
