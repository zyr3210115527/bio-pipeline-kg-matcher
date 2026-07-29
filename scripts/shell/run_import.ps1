#Requires -Version 5.1

<#
.SYNOPSIS
Biomed KG Import Runner (PowerShell)

.DESCRIPTION
This script orchestrates CSV validation, CSV sync to Neo4j import directory,
and Cypher import execution for the biomedical knowledge graph project.

It attempts to load connection configuration from config/neo4j.env.ps1.
Password is handled as SecureString and only converted to plaintext when
calling the Python import runner.

.PARAMETER Neo4jUri
Neo4j bolt URI, e.g. bolt://localhost:7687. Defaults to $env:NEO4J_URI

.PARAMETER Neo4jUser
Neo4j username. Defaults to $env:NEO4J_USER

.PARAMETER Neo4jDatabase
Neo4j database name. Defaults to $env:NEO4J_DATABASE or 'neo4j'

.PARAMETER Neo4jImportDir
Neo4j import directory path. Defaults to $env:NEO4J_IMPORT_DIR

.PARAMETER Neo4jPassword
Neo4j password as SecureString. If not provided, will try $env:NEO4J_PASSWORD
or prompt interactively.

.PARAMETER RunClear
If specified, will run 00_clear.cypher to clear the database before import.

.PARAMETER SkipValidate
If specified, will skip CSV validation step.

.PARAMETER OpenBrowser
If specified, will open Neo4j Browser after import completes.

.EXAMPLE
.\scripts\shell\run_import.ps1

.EXAMPLE
.\scripts\shell\run_import.ps1 -RunClear -OpenBrowser
#>

param(
    [string]$Neo4jUri = $env:NEO4J_URI,
    [string]$Neo4jUser = $env:NEO4J_USER,
    [string]$Neo4jDatabase = $(if ($env:NEO4J_DATABASE) { $env:NEO4J_DATABASE } else { "neo4j" }),
    [string]$Neo4jImportDir = $env:NEO4J_IMPORT_DIR,
    [SecureString]$Neo4jPassword,
    [switch]$RunClear,
    [switch]$SkipValidate,
    [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"

# --------------------------------------------
# Resolve project paths
# --------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
$CsvRoot = Join-Path $ProjectRoot "data\csv"
$PythonScriptDir = Join-Path $ProjectRoot "scripts\python"

# --------------------------------------------
# Load configuration file if exists
# --------------------------------------------
$ConfigPath = Join-Path $ProjectRoot "config\neo4j.env.ps1"
if (Test-Path $ConfigPath) {
    Write-Host "Loading config from $ConfigPath"
    . $ConfigPath
    
    # Override parameters with config if they were not provided explicitly
    if (-not $PSBoundParameters.ContainsKey('Neo4jUri') -and $env:NEO4J_URI) {
        $Neo4jUri = $env:NEO4J_URI
    }
    if (-not $PSBoundParameters.ContainsKey('Neo4jUser') -and $env:NEO4J_USER) {
        $Neo4jUser = $env:NEO4J_USER
    }
    if (-not $PSBoundParameters.ContainsKey('Neo4jDatabase') -and $env:NEO4J_DATABASE) {
        $Neo4jDatabase = $env:NEO4J_DATABASE
    }
    if (-not $PSBoundParameters.ContainsKey('Neo4jImportDir') -and $env:NEO4J_IMPORT_DIR) {
        $Neo4jImportDir = $env:NEO4J_IMPORT_DIR
    }
}
else {
    Write-Host "Config file not found: $ConfigPath (will use parameters or environment variables)"
}

Write-Host "============================================"
Write-Host "Biomed KG Import Runner (PowerShell)"
Write-Host "============================================"
Write-Host "PROJECT_ROOT      = $ProjectRoot"
Write-Host "CSV_ROOT          = $CsvRoot"
Write-Host "NEO4J_URI         = $Neo4jUri"
Write-Host "NEO4J_USER        = $Neo4jUser"
Write-Host "NEO4J_DATABASE    = $Neo4jDatabase"
Write-Host "NEO4J_IMPORT_DIR  = $Neo4jImportDir"
Write-Host "RUN_CLEAR         = $RunClear"
Write-Host "SKIP_VALIDATE     = $SkipValidate"
Write-Host "OPEN_BROWSER      = $OpenBrowser"
Write-Host "============================================"

# --------------------------------------------
# Validate required parameters
# --------------------------------------------
if (-not $Neo4jUri) {
    throw "Neo4j URI is not set. Provide -Neo4jUri parameter or set NEO4J_URI environment variable or add to config/neo4j.env.ps1"
}
if (-not $Neo4jUser) {
    throw "Neo4j user is not set. Provide -Neo4jUser parameter or set NEO4J_USER environment variable or add to config/neo4j.env.ps1"
}
if (-not $Neo4jImportDir) {
    throw "Neo4j import directory is not set. Provide -Neo4jImportDir parameter or set NEO4J_IMPORT_DIR environment variable or add to config/neo4j.env.ps1"
}

# --------------------------------------------
# Resolve password
# Priority:
# 1. Explicit -Neo4jPassword parameter
# 2. Environment variable NEO4J_PASSWORD (from config or shell)
# 3. Prompt interactively
# --------------------------------------------
if (-not $Neo4jPassword) {
    if ($env:NEO4J_PASSWORD) {
        Write-Host "Using password from NEO4J_PASSWORD environment variable"
        $Neo4jPassword = ConvertTo-SecureString $env:NEO4J_PASSWORD -AsPlainText -Force
    }
    else {
        Write-Host "Neo4j password not provided. Prompting for input..."
        $Neo4jPassword = Read-Host "Enter Neo4j password" -AsSecureString
    }
}

# Convert SecureString to plaintext only when calling Python
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($Neo4jPassword)
try {
    $Neo4jPasswordPlain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

    # --------------------------------------------
    # Step 1: Validate CSV
    # --------------------------------------------
    if (-not $SkipValidate) {
        Write-Host "[1/4] Validating CSV files..."
        $ValidateScript = Join-Path $PythonScriptDir "validate_csv.py"
        if (-not (Test-Path $ValidateScript)) {
            throw "Validation script not found: $ValidateScript"
        }
        python $ValidateScript --project-root $ProjectRoot
        if ($LASTEXITCODE -ne 0) {
            throw "CSV validation failed"
        }
        Write-Host "[1/4] CSV validation passed."
    }
    else {
        Write-Host "[1/4] Skipping CSV validation."
    }

    # --------------------------------------------
    # Step 2: Sync CSV files
    # --------------------------------------------
    Write-Host "[2/4] Syncing CSV files to Neo4j import directory..."

    if (-not (Test-Path $Neo4jImportDir)) {
        throw "Neo4j import directory does not exist: $Neo4jImportDir"
    }

    $ReferenceDir = Join-Path $Neo4jImportDir "reference"
    $EntitiesDir = Join-Path $Neo4jImportDir "entities"
    $RelationsDir = Join-Path $Neo4jImportDir "relations"

    New-Item -ItemType Directory -Force -Path $ReferenceDir | Out-Null
    New-Item -ItemType Directory -Force -Path $EntitiesDir | Out-Null
    New-Item -ItemType Directory -Force -Path $RelationsDir | Out-Null

    $RefCsvPath = Join-Path $CsvRoot "reference\*.csv"
    $EntCsvPath = Join-Path $CsvRoot "entities\*.csv"
    $RelCsvPath = Join-Path $CsvRoot "relations\*.csv"

    if (-not (Test-Path $RefCsvPath)) {
        Write-Warning "No reference CSV files found at $RefCsvPath"
    }
    else {
        Copy-Item $RefCsvPath $ReferenceDir -Force
    }

    if (-not (Test-Path $EntCsvPath)) {
        Write-Warning "No entity CSV files found at $EntCsvPath"
    }
    else {
        Copy-Item $EntCsvPath $EntitiesDir -Force
    }

    if (-not (Test-Path $RelCsvPath)) {
        Write-Warning "No relation CSV files found at $RelCsvPath"
    }
    else {
        Copy-Item $RelCsvPath $RelationsDir -Force
    }

    Write-Host "[2/4] CSV sync completed."

    # --------------------------------------------
    # Step 3: Execute Cypher import files
    # --------------------------------------------
    Write-Host "[3/4] Running Cypher import pipeline..."

    $ImportRunner = Join-Path $PythonScriptDir "import_runner.py"
    if (-not (Test-Path $ImportRunner)) {
        throw "Import runner script not found: $ImportRunner"
    }

    $ArgsList = @(
        $ImportRunner
        "--project-root", $ProjectRoot
        "--uri", $Neo4jUri
        "--user", $Neo4jUser
        "--password", $Neo4jPasswordPlain
        "--database", $Neo4jDatabase
    )

    if ($RunClear) {
        Write-Warning "RunClear flag is set. Database will be cleared before import!"
        $ArgsList += "--run-clear"
    }

    python @ArgsList
    if ($LASTEXITCODE -ne 0) {
        throw "Import pipeline failed"
    }

    Write-Host "[3/4] Import pipeline completed."

    # --------------------------------------------
    # Step 4: Done
    # --------------------------------------------
    Write-Host "[4/4] Done."
    Write-Host "Import finished successfully."

    # --------------------------------------------
    # Optional: Open Neo4j Browser
    # --------------------------------------------
    if ($OpenBrowser) {
        Write-Host "Opening Neo4j Browser..."
        Start-Process "http://localhost:7474"
    }
}
catch {
    Write-Error "Import failed: $_"
    throw
}
finally {
    if ($BSTR -ne [IntPtr]::Zero) {
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
    }
}