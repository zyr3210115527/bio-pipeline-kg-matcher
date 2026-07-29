# 创建脚本内容
@'
param(
    [string]$RootPath = ".",
    [int]$MaxDepth = 5,
    [switch]$DryRun
)

function Clean-CSV {
    param(
        [string]$filePath,
        [int]$currentDepth
    )
    
    try {
        Write-Host ("  " * $currentDepth + "Cleaning: $filePath") -ForegroundColor Cyan
        
        if ($DryRun) {
            Write-Host ("  " * $currentDepth + "[DRY RUN] Would clean: $filePath") -ForegroundColor Yellow
            return $true
        }
        
        $content = Get-Content $filePath -Raw -ErrorAction Stop
        $originalSize = $content.Length
        
        $clean = $content -replace '^\xEF\xBB\xBF', '' `
                          -replace '[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '' `
                          -replace '[\u200B-\u200F\uFEFF]', '' `
                          -replace '(?<=,|^)\s+|\s+(?=,|$)', ''
        
        $clean = $clean -replace '\r\n', "`n" -replace '\r', "`n" -replace "`n", "`r`n"
        
        if ($clean.Length -ne $originalSize -or $content -ne $clean) {
            $utf8NoBom = New-Object System.Text.UTF8Encoding $false
            [System.IO.File]::WriteAllText($filePath, $clean, $utf8NoBom)
            Write-Host ("  " * $currentDepth + "  ✓ Cleaned") -ForegroundColor Green
        } else {
            Write-Host ("  " * $currentDepth + "  ○ No changes") -ForegroundColor Gray
        }
        
        return $true
    }
    catch {
        Write-Host ("  " * $currentDepth + "  ✗ Error: $($_.Exception.Message)") -ForegroundColor Red
        return $false
    }
}

function Get-CSVFilesRecursive {
    param(
        [string]$path,
        [int]$currentDepth,
        [int]$maxDepth
    )
    
    if ($currentDepth -gt $maxDepth) {
        return @()
    }
    
    $files = @()
    
    if (Test-Path $path) {
        $files += Get-ChildItem -Path $path -Filter "*.csv" -File -ErrorAction SilentlyContinue | 
                  ForEach-Object { [PSCustomObject]@{Path = $_.FullName; Depth = $currentDepth} }
        
        $subDirs = Get-ChildItem -Path $path -Directory -ErrorAction SilentlyContinue
        foreach ($dir in $subDirs) {
            $files += Get-CSVFilesRecursive -path $dir.FullName -currentDepth ($currentDepth + 1) -maxDepth $maxDepth
        }
    }
    
    return $files
}

Write-Host "========================================" -ForegroundColor Magenta
Write-Host "CSV Recursive Cleaner (Max Depth: $MaxDepth)" -ForegroundColor Cyan
Write-Host "Root Path: $(Resolve-Path $RootPath)" -ForegroundColor Cyan
if ($DryRun) {
    Write-Host "Mode: DRY RUN (Preview only)" -ForegroundColor Yellow
}
Write-Host "========================================" -ForegroundColor Magenta
Write-Host ""

$allFiles = Get-CSVFilesRecursive -path $RootPath -currentDepth 1 -maxDepth $MaxDepth

Write-Host "Found $($allFiles.Count) CSV files to process" -ForegroundColor Green
Write-Host ""

$successCount = 0
$failCount = 0

foreach ($file in $allFiles) {
    $result = Clean-CSV -filePath $file.Path -currentDepth $file.Depth
    if ($result) {
        $successCount++
    } else {
        $failCount++
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Magenta
Write-Host "Summary:" -ForegroundColor Cyan
Write-Host "  Total files: $($allFiles.Count)" -ForegroundColor White
Write-Host "  Successfully cleaned: $successCount" -ForegroundColor Green
Write-Host "  Failed: $failCount" -ForegroundColor $(if ($failCount -gt 0) { "Red" } else { "Green" })
Write-Host "========================================" -ForegroundColor Magenta
'@ | Out-File -FilePath "RecursiveClean-CSV.ps1" -Encoding UTF8

Write-Host "Script created successfully!" -ForegroundColor Green