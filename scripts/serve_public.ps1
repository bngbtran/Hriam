<#
  Bat Hriam thanh server cong khai: backend (API + giao dien) + Cloudflare Tunnel.

    powershell -ExecutionPolicy Bypass -File scripts\serve_public.ps1          # bat, in link cong khai
    powershell -ExecutionPolicy Bypass -File scripts\serve_public.ps1 -Stop    # tat ca

  Link dang https://xxxx.trycloudflare.com, DOI moi lan bat lai. Link duoc ghi vao backend\storage\public_url.txt
  va chep vao clipboard. Hai tien trinh duoc tach han (qua WMI): dong cua so nay, dong VS Code hay ket thuc phien Claude Code van chay tiep.
  Bien moi truong tuy chon: HRIAM_PY = duong dan python (mac dinh: conda env msa).
#>
param([switch]$Stop)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$storage = Join-Path $root "backend\storage"
$urlFile = Join-Path $storage "public_url.txt"
$tunnelLog = Join-Path $storage "tunnel.log"
New-Item -ItemType Directory -Force $storage | Out-Null

function Stop-Hriam {
    Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
    $c = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($c) { Stop-Process -Id $c.OwningProcess -Force }
    Remove-Item $urlFile -ErrorAction SilentlyContinue
}


# Chay tien trinh TACH HAN khoi cua so/terminal goi script (qua WMI): dong terminal, dong VS Code hay ket thuc
# phien Claude Code deu khong lam tat server. Start-Process thuong thi tien trinh con co the bi tat theo.
function Start-Detached([string]$CommandLine, [string]$WorkDir) {
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $CommandLine; CurrentDirectory = $WorkDir }
    if ($r.ReturnValue -ne 0) { throw "Khong khoi dong duoc: $CommandLine (ma loi $($r.ReturnValue))" }
}

if ($Stop) { Stop-Hriam; Write-Host "Da tat server va tunnel."; exit 0 }

# --- tim python va cloudflared ---
$py = if ($env:HRIAM_PY) { $env:HRIAM_PY } else { Join-Path $env:USERPROFILE "miniconda3\envs\msa\python.exe" }
if (-not (Test-Path $py)) { throw "Khong thay python o $py. Dat bien HRIAM_PY tro toi python cua moi truong msa." }
$cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cf) { $cf = "C:\Program Files (x86)\cloudflared\cloudflared.exe" }
if (-not (Test-Path $cf)) { throw "Chua cai cloudflared. Chay: winget install --id Cloudflare.cloudflared" }

# --- build giao dien neu chua co ---
if (-not (Test-Path (Join-Path $root "frontend\dist\index.html"))) {
    Write-Host "Chua co frontend\dist, dang build..."
    Push-Location (Join-Path $root "frontend")
    npm install --no-audit --no-fund
    npm run build
    Pop-Location
}

# --- khoi dong lai sach se ---
Stop-Hriam
Write-Host "Dang khoi dong backend..."
Start-Detached "cmd.exe /c set PYTHONUTF8=1&& set PYTHONIOENCODING=utf-8&& `"$py`" -m uvicorn app.main:app --host 127.0.0.1 --port 8000" (Join-Path $root "backend")

$ok = $false
foreach ($i in 1..40) {
    try { if ((Invoke-WebRequest "http://127.0.0.1:8000/api/v1/health" -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200) { $ok = $true; break } } catch { Start-Sleep 2 }
}
if (-not $ok) { throw "Backend khong len duoc. Chay tay de xem loi: cd backend; python -m uvicorn app.main:app" }
Write-Host "Backend OK."

Write-Host "Dang mo tunnel Cloudflare..."
Remove-Item $tunnelLog -ErrorAction SilentlyContinue
Start-Detached "cmd.exe /c `"`"$cf`" tunnel --url http://127.0.0.1:8000 --no-autoupdate 2> `"$tunnelLog`"`"" $root

$url = $null
foreach ($i in 1..30) {
    Start-Sleep 2
    if (Test-Path $tunnelLog) {
        $m = Select-String -Path $tunnelLog -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($m) { $url = $m.Matches[0].Value; break }
    }
}
if (-not $url) { throw "Khong lay duoc link tunnel. Xem $tunnelLog" }

Set-Content -Path $urlFile -Value $url -Encoding ascii
Set-Clipboard -Value $url
Write-Host ""
Write-Host "==============================================="
Write-Host " LINK CONG KHAI: $url"
Write-Host " (da chep vao clipboard, luu o $urlFile)"
Write-Host "==============================================="
Write-Host "Luu y: may nay phai bat va khong ngu (sleep). Tat: them -Stop."
Write-Host "Neu may ban chua mo duoc link (loi DNS), chay: ipconfig /flushdns va doi 1-2 phut."
