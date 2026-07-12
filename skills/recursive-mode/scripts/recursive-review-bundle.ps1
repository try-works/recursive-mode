[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RunId,
    [Parameter(Mandatory = $true)][string]$Phase,
    [Parameter(Mandatory = $true)][string]$Role,
    [Parameter(Mandatory = $true)][string]$ArtifactPath,
    [string]$RepoRoot = (Get-Location).Path,
    [string[]]$UpstreamArtifact = @(),
    [string[]]$Addendum = @(),
    [string[]]$PriorRef = @(),
    [string[]]$ControlDoc = @(),
    [string[]]$CodeRef = @(),
    [string[]]$EvidenceRef = @(),
    [string[]]$AuditQuestion = @(),
    [string[]]$RequiredOutput = @(),
    [string]$RoutingConfigPath = "",
    [string]$RoutingDiscoveryPath = "",
    [string]$RoutedCli = "",
    [string]$RoutedModel = "",
    [string]$OutputName = "",
    [switch]$NoAutoAddenda
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$python = if ($env:PYTHON) { $env:PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { $null }
if (-not $python) {
    Write-Host "[FAIL] Python executable not found in PATH."
    exit 1
}

$scriptPath = Join-Path $PSScriptRoot "recursive-review-bundle.py"
$argsList = @(
    $scriptPath,
    "--repo-root", $RepoRoot,
    "--run-id", $RunId,
    "--phase", $Phase,
    "--role", $Role,
    "--artifact-path", $ArtifactPath
)
if ($OutputName) { $argsList += @("--output-name", $OutputName) }
if ($NoAutoAddenda.IsPresent) { $argsList += "--no-auto-addenda" }
foreach ($value in @($UpstreamArtifact)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--upstream-artifact", $piece.Trim()) } } }
foreach ($value in @($Addendum)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--addendum", $piece.Trim()) } } }
foreach ($value in @($PriorRef)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--prior-ref", $piece.Trim()) } } }
foreach ($value in @($ControlDoc)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--control-doc", $piece.Trim()) } } }
foreach ($value in @($CodeRef)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--code-ref", $piece.Trim()) } } }
foreach ($value in @($EvidenceRef)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--evidence-ref", $piece.Trim()) } } }
foreach ($value in @($AuditQuestion)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--audit-question", $piece.Trim()) } } }
foreach ($value in @($RequiredOutput)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--required-output", $piece.Trim()) } } }
if ($RoutingConfigPath) { $argsList += @("--routing-config-path", $RoutingConfigPath) }
if ($RoutingDiscoveryPath) { $argsList += @("--routing-discovery-path", $RoutingDiscoveryPath) }
if ($RoutedCli) { $argsList += @("--routed-cli", $RoutedCli) }
if ($RoutedModel) { $argsList += @("--routed-model", $RoutedModel) }

& $python @argsList
exit $LASTEXITCODE
