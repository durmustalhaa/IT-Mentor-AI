# Masaustunde "IT Mentor AI" kisayolu olusturur - cift tiklaninca konsol
# penceresi acmadan (pythonw.exe) gui_app.py'yi baslatir. Yeniden calistirmak
# kisayolu gunceller (var olan .lnk'yi siler, ayni ayarlarla yeniden yazar).
#
# pythonw.exe, PATH'teki "python" komutuyla ayni klasorden otomatik tespit
# edilir (conda/venv/sistem Python'i fark etmeksizin, ikisi ayni klasorde
# durur) - elle duzenleme gerekmiyor.
#
# PATH'teki ILK "python" eslesmesi guvenilir olmayabilir: Windows 10/11
# varsayilan olarak "python" icin bos bir Microsoft Store yonlendirici
# (stub) barindirir, gercek bir Python kurulu olsa bile PATH sirasina gore
# once o bulunabilir. Bu yuzden TUM eslesmeler taranir, yaninda gercekten
# pythonw.exe olan ILK gercek Python secilir.

$ProjectRoot = Split-Path -Parent $PSScriptRoot

$PythonwExe = $null
foreach ($candidate in (Get-Command python -All -ErrorAction SilentlyContinue)) {
    $candidatePythonw = Join-Path (Split-Path $candidate.Source) "pythonw.exe"
    if (Test-Path $candidatePythonw) {
        $PythonwExe = $candidatePythonw
        break
    }
}

if (-not $PythonwExe) {
    Write-Output "HATA: Calisan bir Python kurulumu bulunamadi (PATH'teki 'python' bos bir yonlendirici olabilir)."
    Write-Output "Python kurun: https://www.python.org/downloads/ (kurulumda 'Add python.exe to PATH' isaretli olsun)"
    exit 1
}

$GuiScript = Join-Path $ProjectRoot "scripts\gui_app.py"
$IconPath = Join-Path $ProjectRoot "assets\app_icon.ico"
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopPath "IT Mentor AI.lnk"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonwExe
$Shortcut.Arguments = "`"$GuiScript`""
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.IconLocation = $IconPath
$Shortcut.Description = "IT Mentor AI - offline IT-ops asistani"
$Shortcut.Save()

Write-Output "Kisayol olusturuldu: $ShortcutPath"
