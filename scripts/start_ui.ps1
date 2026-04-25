$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$DepsPath = Join-Path $ProjectRoot ".tmp\pydeps"
$PythonExe = "C:\Users\hp\anaconda3\python.exe"
$LogPath = Join-Path $ProjectRoot ".tmp\streamlit-ui.log"

Set-Location $ProjectRoot
$env:PYTHONPATH = $DepsPath

& $PythonExe -m streamlit run "ui\app.py" --server.headless true --server.port 8501 --server.address 127.0.0.1 *>&1 |
    Tee-Object -FilePath $LogPath
