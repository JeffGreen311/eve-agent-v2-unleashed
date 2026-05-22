$files = @("eve_server.py", "web\index.html", "run.py", ".env")
foreach ($f in $files) {
    if (-not (Test-Path $f)) { Write-Host "SKIP_MISSING: $f"; continue }
    $bytes = [System.IO.File]::ReadAllBytes($f)
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        $bytes = $bytes[3..($bytes.Length-1)]
    }
    $text = [System.Text.Encoding]::UTF8.GetString($bytes)
    $hasMojibake = ($text -match 'â•|â€“|â€”|â€"|â€™|â€œ|â€')
    if (-not $hasMojibake) { Write-Host "CLEAN_SKIP: $f"; continue }
    $fixed = [System.Text.Encoding]::GetEncoding(1252).GetBytes($text)
    [System.IO.File]::WriteAllBytes($f, $fixed)
    Write-Host "REPAIRED: $f (was $($bytes.Length) bytes, now $($fixed.Length) bytes)"
}
$b = [System.IO.File]::ReadAllBytes("eve_server.py")
$h = 0; for ($i=0; $i -lt $b.Length - 2; $i++) { if ($b[$i] -eq 0xE2 -and $b[$i+1] -eq 0x95 -and $b[$i+2] -eq 0x90) { $h++ } }
$c = 0; for ($i=0; $i -lt $b.Length - 4; $i++) { if ($b[$i] -eq 0xC3 -and $b[$i+1] -eq 0xA2 -and $b[$i+2] -eq 0xE2 -and $b[$i+3] -eq 0x80 -and $b[$i+4] -eq 0xA2) { $c++ } }
Write-Host "VERIFY_eve_server.py: healthy_box_chars=$h corrupt_mojibake=$c"
