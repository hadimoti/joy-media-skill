param([string]$Root,[string]$Out)
if (Test-Path $Out) { throw 'output exists' }
Get-ChildItem -LiteralPath $Root -Recurse -Force -ErrorAction SilentlyContinue | ForEach-Object {
  [pscustomobject]@{ path = $_.FullName; len = $(if ($_.PSIsContainer) { -1 } else { $_.Length }); mtime = $_.LastWriteTimeUtc.ToString('o') }
} | Export-Csv -LiteralPath $Out -NoTypeInformation
