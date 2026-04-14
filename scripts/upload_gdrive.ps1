# Upload CrimsonDesertData_0015 split archives to Google Drive
#
# Prerequisites:
#   1. Install rclone: winget install Rclone.Rclone
#   2. Configure Google Drive: rclone config
#      - Choose "n" for new remote
#      - Name: "gdrive"
#      - Storage type: "drive" (Google Drive)
#      - Follow OAuth2 browser prompts
#   3. Run this script: powershell -ExecutionPolicy Bypass -File scripts\upload_gdrive.ps1
#
# The script uploads all .7z.* parts to a "CrimsonDesertUnpacker" folder on Google Drive.

param(
    [string]$RemoteName = "gdrive",
    [string]$RemoteFolder = "CrimsonDesertUnpacker/CrimsonDesertData_0015",
    [string]$LocalPattern = "CrimsonDesertData_0015.7z.*"
)

# Check rclone
$rclonePath = Get-Command rclone -ErrorAction SilentlyContinue
if (-not $rclonePath) {
    Write-Host "ERROR: rclone not found. Install with: winget install Rclone.Rclone" -ForegroundColor Red
    Write-Host "Then restart your shell and run: rclone config" -ForegroundColor Yellow
    exit 1
}

# Check if remote is configured
$remotes = & rclone listremotes 2>&1
if ($remotes -notmatch "$RemoteName`:") {
    Write-Host "ERROR: Remote '$RemoteName' not configured." -ForegroundColor Red
    Write-Host "Run 'rclone config' to set up Google Drive first." -ForegroundColor Yellow
    exit 1
}

# Find files to upload
$files = Get-ChildItem -Path $LocalPattern -ErrorAction SilentlyContinue | Sort-Object Name
if ($files.Count -eq 0) {
    Write-Host "ERROR: No files matching '$LocalPattern' found." -ForegroundColor Red
    Write-Host "Run the compression script first: powershell -File scripts\compress_0015.ps1" -ForegroundColor Yellow
    exit 1
}

$totalSize = ($files | Measure-Object -Property Length -Sum).Sum
Write-Host "Found $($files.Count) files to upload (total: $([math]::Round($totalSize / 1GB, 2)) GB)" -ForegroundColor Cyan
Write-Host "Uploading to ${RemoteName}:${RemoteFolder}/" -ForegroundColor Cyan
Write-Host ""

# Upload each file
$uploaded = 0
foreach ($file in $files) {
    $sizeGB = [math]::Round($file.Length / 1GB, 2)
    Write-Host "[$($uploaded + 1)/$($files.Count)] Uploading $($file.Name) ($sizeGB GB)..." -ForegroundColor White

    & rclone copy $file.FullName "${RemoteName}:${RemoteFolder}/" --progress --transfers 1

    if ($LASTEXITCODE -eq 0) {
        $uploaded++
        Write-Host "  Done!" -ForegroundColor Green
    } else {
        Write-Host "  Failed! (exit code: $LASTEXITCODE)" -ForegroundColor Red
        Write-Host "  Retry with: rclone copy '$($file.FullName)' '${RemoteName}:${RemoteFolder}/'" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Upload complete: $uploaded/$($files.Count) files uploaded successfully." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Open Google Drive and find the '$RemoteFolder' folder" -ForegroundColor White
Write-Host "2. Right-click the folder > Share > Copy link" -ForegroundColor White
Write-Host "3. Update README.md with the share link" -ForegroundColor White
