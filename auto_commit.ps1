# Auto-commit script for ADB projects (Python + C#)
$repoPaths = @(
    "E:\DOWNLOADS\CREATIVE\PYTHON\GitHub\ADB",           # Python версия
    "E:\DOWNLOADS\CREATIVE\PYTHON\GitHub\ADB\dotnet"    # C# версия
)
$date = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

foreach ($repoPath in $repoPaths) {
    if (-not (Test-Path $repoPath)) {
        Write-Host "[$date] Repo not found: $repoPath"
        continue
    }

    Set-Location $repoPath
    $repoName = Split-Path $repoPath -Leaf

    # Check for changes
    $status = git status --porcelain
    if (-not $status) {
        Write-Host "[$date] [$repoName] No changes to commit"
        continue
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

    Write-Host "[$date] [$repoName] Committed and pushed: $msg"
}
