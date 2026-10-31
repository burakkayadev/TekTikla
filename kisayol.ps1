# Masaüstüne TekTıkla simgeli kısayol oluşturur (konsol penceresi açmadan başlatır).
$app = $PSScriptRoot
$python = Join-Path $app ".venv\Scripts\pythonw.exe"
$icon = Join-Path $app "assets\tektikla.ico"
if (-not (Test-Path $icon)) {
    & (Join-Path $app ".venv\Scripts\python.exe") -c "import sys; sys.path.insert(0, r'$app'); from tektikla.app import ensure_icon; ensure_icon()"
}
$shell = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath("Desktop")
$link = $shell.CreateShortcut((Join-Path $desktop "TekTıkla.lnk"))
$exe = Join-Path $app "dist\TekTikla\TekTikla.exe"
if (Test-Path $exe) {
    # Derlenmiş exe varsa onu aç (simgesi exe'nin içinde)
    $link.TargetPath = $exe
    $link.Arguments = ""
    $link.WorkingDirectory = Split-Path $exe
    $link.IconLocation = "$exe,0"
} else {
    $link.TargetPath = $python
    $link.Arguments = "`"$(Join-Path $app 'tektikla.py')`""
    $link.WorkingDirectory = $app
    $link.IconLocation = $icon
}
$link.Description = "TekTıkla - Bütün sitelerden video indir"
$link.Save()
Write-Host "Kısayol oluşturuldu: $desktop\TekTıkla.lnk"
