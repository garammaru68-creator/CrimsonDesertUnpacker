# Compress CrimsonDesertData/0015 into split archives for Google Drive upload
# Each part will be ~1.9GB to stay under Google Drive's 2GB upload limit
#
# Usage: powershell -ExecutionPolicy Bypass -File scripts\compress_0015.ps1
#
# After compression, upload the .7z.* files to Google Drive manually.
# To extract: 7z x CrimsonDesertData_0015.7z.001

$SourceDir = "CrimsonDesertData\0015"
$OutputBase = "CrimsonDesertData_0015"
$SplitSize = "1900m"  # 1.9GB per part

# Check if 7z is available
$7zPath = Get-Command 7z -ErrorAction SilentlyContinue
if (-not $7zPath) {
    $7zPath = "C:\Program Files\7-Zip\7z.exe"
    if (-not (Test-Path $7zPath)) {
        Write-Host "ERROR: 7-Zip not found. Install from https://www.7-zip.org/" -ForegroundColor Red
        exit 1
    }
} else {
    $7zPath = $7zPath.Source
}

if (-not (Test-Path $SourceDir)) {
    Write-Host "ERROR: $SourceDir not found" -ForegroundColor Red
    exit 1
}

Write-Host "Compressing $SourceDir into split archives ($SplitSize each)..." -ForegroundColor Cyan
Write-Host "This will take a while for 46GB+ of data." -ForegroundColor Yellow

& $7zPath a -t7z -v"$SplitSize" -mx=1 -mmt=on "$OutputBase.7z" "$SourceDir\*"

if ($LASTEXITCODE -eq 0) {
    $parts = Get-ChildItem "$OutputBase.7z.*" | Sort-Object Name
    Write-Host "`nCompression complete! $($parts.Count) parts created:" -ForegroundColor Green
    $parts | ForEach-Object { Write-Host "  $($_.Name) - $([math]::Round($_.Length / 1GB, 2)) GB" }
    Write-Host "`nUpload these files to Google Drive, then update README.md with the share link." -ForegroundColor Cyan
} else {
    Write-Host "Compression failed with exit code $LASTEXITCODE" -ForegroundColor Red
}
