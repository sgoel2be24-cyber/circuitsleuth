param(
    [switch]$IncludeMcp,
    [string]$ApiBase = 'http://127.0.0.1:8100'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$projectPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    throw 'Create .venv and install backend/requirements.lock.txt before verification.'
}

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Program failed with exit code $LASTEXITCODE."
    }
}

Push-Location -LiteralPath $projectRoot
try {
    Invoke-Checked $projectPython @('-m', 'pip', 'check')
    Invoke-Checked $projectPython @('-c', "import cv2; print('OpenCV', cv2.__version__); assert cv2.__version__.startswith('5.'), 'OpenCV 5 is required'")
    Invoke-Checked $projectPython @('-m', 'pytest', 'backend/tests', '-q')
    Push-Location -LiteralPath (Join-Path $projectRoot 'frontend')
    try {
        Invoke-Checked 'npm.cmd' @('run', 'lint')
        Invoke-Checked 'npm.cmd' @('run', 'build')
    } finally {
        Pop-Location
    }
    if ($IncludeMcp) {
        # The smoke test starts its own stdio server and uses temporary data.
        # ApiBase is retained as a compatible parameter for existing callers.
        Invoke-Checked $projectPython @('tools/mcp_smoke_test.py')
    }
    Write-Host 'Local checks passed. Container and AWS execution were not checked.' -ForegroundColor Green
} finally {
    Pop-Location
}
