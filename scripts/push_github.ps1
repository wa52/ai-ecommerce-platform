# Publish this project to GitHub.
#
# The project lives inside the D:\AiProjects umbrella repo. To avoid a nested
# git repo (which would make the umbrella report hundreds of deletions), this
# script uses `git subtree split` to extract an isolated history for this
# project path, then pushes it to the standalone remote repo.
#
# Usage (run from the project directory):
#   powershell -File scripts\push_github.ps1 -Message "feat(xxx): ..."
#
# Requirements: `gh auth login` already done. The script commits only this
# project path in the umbrella repo.

param(
    [Parameter(Mandatory = $true)][string]$Message,
    [string]$ProjectPath = "",
    [string]$RemoteUrl = "https://github.com/wa52/ai-ecommerce-platform.git",
    [string]$Prefix = "AI e-commerce platform",
    [string]$SplitBranch = "ai-ecommerce-main"
)

$ErrorActionPreference = "Stop"

if (-not $ProjectPath) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $ProjectPath = Split-Path -Parent $scriptDir
}
$ProjectPath = (Resolve-Path $ProjectPath).Path

$umbrellaRoot = (git -C $ProjectPath rev-parse --show-toplevel).Trim()
Write-Host "umbrella root: $umbrellaRoot"

git -C $umbrellaRoot add -- "$Prefix"

$staged = git -C $umbrellaRoot diff --cached --name-only -- "$Prefix"
if (-not $staged) {
    Write-Host "no staged changes for this project; skipping commit"
} else {
    git -C $umbrellaRoot commit -m $Message | Out-Host
}

git -C $umbrellaRoot branch -D $SplitBranch 2>$null | Out-Null
git -C $umbrellaRoot subtree split -P "$Prefix" -b $SplitBranch | Out-Null

# subtree split is deterministic, so the new split branch is normally a
# fast-forward of the previously pushed main. Try a normal push first and only
# force when the remote has diverged (e.g. after a rewrite).
git -C $umbrellaRoot push $RemoteUrl "${SplitBranch}:main"
if ($LASTEXITCODE -ne 0) {
    Write-Host "push rejected; retrying with --force-with-lease"
    git -C $umbrellaRoot fetch $RemoteUrl main
    git -C $umbrellaRoot push --force-with-lease $RemoteUrl "${SplitBranch}:main"
}
Write-Host "pushed to main"
