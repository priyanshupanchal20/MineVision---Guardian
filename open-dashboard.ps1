# Find the MineVision Pi on the current Wi-Fi and open the dashboard.
# Works on home / college / phone hotspot — no fixed IP required.
$ErrorActionPreference = "SilentlyContinue"
$names = @(
  "http://minevision.local:8000",
  "http://darshan.local:8000",
  "http://raspberrypi.local:8000",
  "http://minevision.local:8000"
)
$oui = @(
  "B8-27-EB", "DC-A6-32", "E4-5F-01", "28-CD-C1",
  "D8-3A-DD", "2C-CF-67", "B8-27-EB", "E4-5F-01"
)

function Test-Url([string]$url) {
  try {
    $r = Invoke-WebRequest -Uri ($url.TrimEnd("/") + "/api/v1/health") -TimeoutSec 2 -UseBasicParsing
    return $r.StatusCode -eq 200
  } catch {
    return $false
  }
}

$tried = New-Object System.Collections.Generic.List[string]
foreach ($u in $names) { $tried.Add($u) }

# Force a fresh ARP pass so a newly joined Pi shows up.
try {
  Get-NetNeighbor -AddressFamily IPv4 -ErrorAction SilentlyContinue | Out-Null
} catch {}
arp -a | ForEach-Object {
  if ($_ -notmatch "(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]{11,17})") { return }
  $ip = $Matches[1]
  $mac = $Matches[2].ToUpper()
  foreach ($p in $oui) {
    if ($mac.StartsWith($p)) {
      $tried.Add("http://${ip}:8000")
      break
    }
  }
}

Write-Host "Looking for MineVision on this Wi-Fi..."
for ($round = 1; $round -le 3; $round++) {
  foreach ($u in $tried) {
    Write-Host "  try $u"
    if (Test-Url $u) {
      Write-Host "OPEN $u"
      Start-Process $u
      exit 0
    }
  }
  if ($round -lt 3) {
    Write-Host "  retrying ($round/3)..."
    Start-Sleep -Seconds 2
  }
}

Write-Host ""
Write-Host "Dashboard not found on this Wi-Fi."
Write-Host "1. Laptop and Pi must be on the SAME network (not guest/client-isolation)."
Write-Host "2. On the Pi (HDMI/SSH), join that Wi-Fi:"
Write-Host "     sudo bash ~/MineTruck/MineTruck\ Project/raspberry_pi/scripts/join-wifi.sh \"SSID\" \"password\""
Write-Host "3. One-time auto-start + mDNS:"
Write-Host "     sudo bash ~/MineTruck/MineTruck\ Project/raspberry_pi/scripts/setup-dashboard-autostart.sh"
Write-Host "4. Then open http://minevision.local:8000"
exit 1
