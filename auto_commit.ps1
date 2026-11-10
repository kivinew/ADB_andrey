# Auto-commit script for ADB project
$repoPath = "E:\DOWNLOADS\CREATIVE\PYTHON\GitHub\ADB"
$date = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

Set-Location $repoPath

# Check for changes
$status = git status --porcelain
if (-not $status) {
    Write-Host "[$date] No changes to commit"
    exit 0
}

# Add all changes
git add -A

# Commit with timestamp
$msg = "Auto-commit: $date"
git commit -m "$msg"

# Push to remote (if configured)
$remote = git remote
if ($remote) {
    git push
}

Write-Host "[$date] Committed and pushed: $msg"