[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RunId,
    [Parameter(Mandatory = $true)][string]$SubagentId,
    [Parameter(Mandatory = $true)][string]$Phase,
    [Parameter(Mandatory = $true)][string]$Purpose,
    [Parameter(Mandatory = $true)][string]$ExecutionMode,
    [string]$ArtifactPath = "",
    [string]$RepoRoot = (Get-Location).Path,
    [string[]]$UpstreamArtifact = @(),
    [string[]]$Addendum = @(),
    [string]$ReviewBundle = "",
    [string]$DiffBasis = "",
    [string[]]$CodeRef = @(),
    [string[]]$MemoryRef = @(),
    [string[]]$AuditQuestion = @(),
    [string[]]$ActionTaken = @(),
    [string[]]$CreatedFile = @(),
    [string[]]$ModifiedFile = @(),
    [string[]]$ReviewedFile = @(),
    [string[]]$UntouchedFile = @(),
    [string[]]$ArtifactRead = @(),
    [string[]]$ArtifactUpdated = @(),
    [string[]]$EvidenceUsed = @(),
    [string[]]$Finding = @(),
    [string[]]$VerificationPath = @(),
    [string[]]$VerificationItem = @(),
    [string]$RouterUsed = "",
    [string]$RoutedRole = "",
    [string]$RoutedCli = "",
    [string]$RoutedModel = "",
    [string]$RoutingConfigPath = "",
    [string]$RoutingDiscoveryPath = "",
    [string]$RoutingResolutionBasis = "",
    [string]$RoutingFallbackReason = "",
    [string]$CliProbeSummary = "",
    [string]$PromptBundlePath = "",
    [string]$InvocationExitCode = "",
    [string[]]$OutputCapturePath = @(),
    [string]$OutputName = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$python = if ($env:PYTHON) { $env:PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { $null }
if (-not $python) {
    Write-Host "[FAIL] Python executable not found in PATH."
    exit 1
}

$scriptPath = Join-Path $PSScriptRoot "recursive-subagent-action.py"
$argsList = @(
    $scriptPath,
    "--repo-root", $RepoRoot,
    "--run-id", $RunId,
    "--subagent-id", $SubagentId,
    "--phase", $Phase,
    "--purpose", $Purpose,
    "--execution-mode", $ExecutionMode
)

if ($ArtifactPath) { $argsList += @("--artifact-path", $ArtifactPath) }
if ($ReviewBundle) { $argsList += @("--review-bundle", $ReviewBundle) }
if ($DiffBasis) { $argsList += @("--diff-basis", $DiffBasis) }
if ($OutputName) { $argsList += @("--output-name", $OutputName) }
if ($RouterUsed) { $argsList += @("--router-used", $RouterUsed) }
if ($RoutedRole) { $argsList += @("--routed-role", $RoutedRole) }
if ($RoutedCli) { $argsList += @("--routed-cli", $RoutedCli) }
if ($RoutedModel) { $argsList += @("--routed-model", $RoutedModel) }
if ($RoutingConfigPath) { $argsList += @("--routing-config-path", $RoutingConfigPath) }
if ($RoutingDiscoveryPath) { $argsList += @("--routing-discovery-path", $RoutingDiscoveryPath) }
if ($RoutingResolutionBasis) { $argsList += @("--routing-resolution-basis", $RoutingResolutionBasis) }
if ($RoutingFallbackReason) { $argsList += @("--routing-fallback-reason", $RoutingFallbackReason) }
if ($CliProbeSummary) { $argsList += @("--cli-probe-summary", $CliProbeSummary) }
if ($PromptBundlePath) { $argsList += @("--prompt-bundle-path", $PromptBundlePath) }
if ($InvocationExitCode) { $argsList += @("--invocation-exit-code", $InvocationExitCode) }

foreach ($value in @($UpstreamArtifact)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--upstream-artifact", $piece.Trim()) } } }
foreach ($value in @($Addendum)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--addendum", $piece.Trim()) } } }
foreach ($value in @($CodeRef)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--code-ref", $piece.Trim()) } } }
foreach ($value in @($MemoryRef)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--memory-ref", $piece.Trim()) } } }
foreach ($value in @($AuditQuestion)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--audit-question", $piece.Trim()) } } }
foreach ($value in @($ActionTaken)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--action-taken", $piece.Trim()) } } }
foreach ($value in @($CreatedFile)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--created-file", $piece.Trim()) } } }
foreach ($value in @($ModifiedFile)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--modified-file", $piece.Trim()) } } }
foreach ($value in @($ReviewedFile)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--reviewed-file", $piece.Trim()) } } }
foreach ($value in @($UntouchedFile)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--untouched-file", $piece.Trim()) } } }
foreach ($value in @($ArtifactRead)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--artifact-read", $piece.Trim()) } } }
foreach ($value in @($ArtifactUpdated)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--artifact-updated", $piece.Trim()) } } }
foreach ($value in @($EvidenceUsed)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--evidence-used", $piece.Trim()) } } }
foreach ($value in @($Finding)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--finding", $piece.Trim()) } } }
foreach ($value in @($VerificationPath)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--verification-path", $piece.Trim()) } } }
foreach ($value in @($VerificationItem)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--verification-item", $piece.Trim()) } } }
foreach ($value in @($OutputCapturePath)) { foreach ($piece in ($value -split ",")) { if ($piece.Trim()) { $argsList += @("--output-capture-path", $piece.Trim()) } } }

& $python @argsList
exit $LASTEXITCODE
