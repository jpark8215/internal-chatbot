# Knowledge Assistant Deployment Package Creator
# PowerShell script for Windows users

Write-Host "Creating Knowledge Assistant Deployment Package" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green

# Check if we're in the right directory
if (-not (Test-Path "docker-compose.yml")) {
    Write-Host "Error: docker-compose.yml not found!" -ForegroundColor Red
    Write-Host "Please run this script from the project root directory." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Checking required files..." -ForegroundColor Cyan

# Check for required files
$requiredFiles = @(
    "docker-compose.yml",
    "api/Dockerfile",
    "api/requirements.txt",
    "deploy-script.sh",
    "deploy-script.bat",
    ".env.example"
)

$missingFiles = @()
foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        $missingFiles += $file
    }
}

if ($missingFiles.Count -gt 0) {
    Write-Host "Missing required files:" -ForegroundColor Red
    foreach ($file in $missingFiles) {
        Write-Host "   - $file" -ForegroundColor Red
    }
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "All required files found!" -ForegroundColor Green

# Create the ZIP file directly (simpler approach)
$zipName = "knowledge-assistant-deploy-$(Get-Date -Format 'yyyyMMdd-HHmmss').zip"
Write-Host "Creating ZIP package: $zipName" -ForegroundColor Cyan

try {
    # Get all files except excluded ones
    $filesToInclude = Get-ChildItem -Path . -Recurse | Where-Object {
        $item = $_
        $relativePath = $item.FullName.Replace((Get-Location).Path, "").TrimStart("\")
        
        # Exclude patterns
        $exclude = $relativePath -match "\.git" -or 
                   $relativePath -match "__pycache__" -or 
                   $relativePath -match "\.venv" -or 
                   $relativePath -match "\.vscode" -or 
                   $relativePath -match "node_modules" -or 
                   $relativePath -match "\.log$" -or 
                   $relativePath -match "\.tmp$" -or 
                   ($item.Name -eq ".env" -and $item.Name -ne ".env.example")
        
        return -not $exclude -and -not $item.PSIsContainer
    }
    
    # Create a temporary list of files for compression
    $tempFileList = "temp-file-list.txt"
    $filesToInclude | ForEach-Object { $_.FullName } | Out-File -FilePath $tempFileList -Encoding UTF8
    
    # Use robocopy to create a clean copy, then compress
    $tempDir = "temp-deploy"
    if (Test-Path $tempDir) {
        Remove-Item $tempDir -Recurse -Force
    }
    
    # Copy files using PowerShell
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    
    # Copy specific directories and files
    $itemsToCopy = @(
        "api",
        "db", 
        "docker-compose.yml",
        "deploy-script.sh",
        "deploy-script.bat",
        "deployment-guide.md",
        ".env.example",
        "README.md"
    )
    
    foreach ($item in $itemsToCopy) {
        if (Test-Path $item) {
            if (Test-Path $item -PathType Container) {
                # It's a directory
                Copy-Item $item -Destination $tempDir -Recurse -Force
            } else {
                # It's a file
                Copy-Item $item -Destination $tempDir -Force
            }
            Write-Host "   Copied: $item" -ForegroundColor Gray
        }
    }
    
    # Create the ZIP file
    Compress-Archive -Path "$tempDir\*" -DestinationPath $zipName -Force -CompressionLevel Optimal
    
    # Get file size
    $zipSize = (Get-Item $zipName).Length
    $zipSizeMB = [math]::Round($zipSize / 1MB, 2)
    
    Write-Host "Deployment package created successfully!" -ForegroundColor Green
    Write-Host "File: $zipName" -ForegroundColor White
    Write-Host "Size: $zipSizeMB MB" -ForegroundColor White
    
    Write-Host ""
    Write-Host "Package Contents:" -ForegroundColor Cyan
    Write-Host "   - Application code (api/)" -ForegroundColor White
    Write-Host "   - Docker configuration" -ForegroundColor White
    Write-Host "   - Deployment scripts" -ForegroundColor White
    Write-Host "   - Database initialization" -ForegroundColor White
    Write-Host "   - Documentation" -ForegroundColor White
    
    Write-Host ""
    Write-Host "Distribution Instructions:" -ForegroundColor Yellow
    Write-Host "1. Send $zipName to target machines" -ForegroundColor White
    Write-Host "2. Extract the ZIP file" -ForegroundColor White
    Write-Host "3. Run deploy-script.bat (Windows) or ./deploy-script.sh (Linux/macOS)" -ForegroundColor White
    Write-Host "4. Access application at http://localhost:8000" -ForegroundColor White
    
} catch {
    Write-Host "Error creating deployment package: $($_.Exception.Message)" -ForegroundColor Red
} finally {
    # Clean up temporary files
    if (Test-Path $tempDir) {
        Remove-Item $tempDir -Recurse -Force
    }
    if (Test-Path $tempFileList) {
        Remove-Item $tempFileList -Force
    }
}

Write-Host ""
Write-Host "Done! Your deployment package is ready." -ForegroundColor Green
Read-Host "Press Enter to exit"