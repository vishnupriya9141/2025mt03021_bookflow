$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = (Get-Command python -ErrorAction Stop).Source
$env:SERVICE_TOKEN = [guid]::NewGuid().ToString('N')
$env:HOST = '127.0.0.1'
$env:INVENTORY_URL = 'http://127.0.0.1:8001'
$children = @()
try {
    foreach ($service in @(@('inventory-service', '8001'), @('order-service', '8002'))) {
        $env:PORT = $service[1]
        $env:DB_PATH = Join-Path $projectRoot ($service[0] + '/data/service.db')
        $children += Start-Process -FilePath $pythonPath -ArgumentList 'app.py' -WorkingDirectory (Join-Path $projectRoot $service[0]) -WindowStyle Hidden -PassThru
    }
    Write-Host 'Inventory: http://127.0.0.1:8001/books'
    Write-Host 'Orders: http://127.0.0.1:8002/orders'
    Write-Host 'Import the Postman collection, or run python tools/demo.py in another terminal.'
    Write-Host 'Press Ctrl+C to stop both services.'
    while ($true) {
        foreach ($child in $children) { if ($child.HasExited) { throw 'A service exited; check ports 8001 and 8002 are available.' } }
        Start-Sleep -Seconds 1
    }
} finally {
    foreach ($child in $children) { if (-not $child.HasExited) { Stop-Process -Id $child.Id } }
}
