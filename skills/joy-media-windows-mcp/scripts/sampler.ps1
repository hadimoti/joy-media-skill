param([string]$Pattern,[string]$Out,[string]$Stop)
if (Test-Path $Out) { throw 'output exists' }
'time,pid,type,ws_mb,private_mb,enc_sessions,gpu_util,gpu_mem_mb,cpu_s' | Set-Content $Out
$types = @{}
$end = (Get-Date).AddMinutes(60)
$i = 0
$gpu = '0,0,0'
while ((Get-Date) -lt $end -and -not (Test-Path $Stop)) {
  if ($i % 5 -eq 0) {
    $types = @{}
    Get-CimInstance Win32_Process -Filter "Name='electron.exe'" | Where-Object { $_.CommandLine -like $Pattern } | ForEach-Object {
      $t = 'browser'
      if ($_.CommandLine -match '--type=([a-z\-]+)') { $t = $Matches[1] }
      $types[[int]$_.ProcessId] = $t
    }
  }
  $g = (& nvidia-smi --query-gpu=encoder.stats.sessionCount,utilization.gpu,memory.used --format=csv,noheader,nounits 2>$null | Select-Object -First 1)
  if ($g) { $gpu = ($g -replace '\s','') }
  $now = (Get-Date).ToString('o')
  foreach ($procId in @($types.Keys)) {
    $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if ($p) { $ws = [math]::Round($p.WorkingSet64/1MB,1).ToString([Globalization.CultureInfo]::InvariantCulture); $pr = [math]::Round($p.PrivateMemorySize64/1MB,1).ToString([Globalization.CultureInfo]::InvariantCulture); $cpu = [math]::Round($p.TotalProcessorTime.TotalSeconds,2).ToString([Globalization.CultureInfo]::InvariantCulture); "$now,$procId,$($types[$procId]),$ws,$pr,$gpu,$cpu" | Add-Content $Out }
  }
  $i++
  Start-Sleep -Milliseconds 1000
}
