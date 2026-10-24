param([string]$Profile = 'bookflow')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
foreach ($tool in @('docker', 'kubectl', 'minikube')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "Install $tool first. See README.md." }
}
function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}
Invoke-Checked 'minikube' @('start', '-p', $Profile, '--driver=docker', '--cpus=2', '--memory=3072')
Invoke-Checked 'minikube' @('-p', $Profile, 'image', 'build', '-t', 'bookflow-inventory:1.0', './inventory-service')
Invoke-Checked 'minikube' @('-p', $Profile, 'image', 'build', '-t', 'bookflow-orders:1.0', './order-service')
Invoke-Checked 'kubectl' @('--context', $Profile, 'apply', '-f', 'k8s/namespace.yaml')
$secretExists = & kubectl --context $Profile -n bookflow get secret service-auth --ignore-not-found -o name
if ($LASTEXITCODE -ne 0) { throw 'Unable to check service secret' }
if (-not $secretExists) {
    $serviceToken = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
    Invoke-Checked 'kubectl' @('--context', $Profile, '-n', 'bookflow', 'create', 'secret', 'generic', 'service-auth', "--from-literal=token=$serviceToken")
}
Invoke-Checked 'kubectl' @('--context', $Profile, 'apply', '-f', 'k8s/workloads.yaml')
foreach ($deployment in @('inventory', 'orders')) {
    Invoke-Checked 'kubectl' @('--context', $Profile, '-n', 'bookflow', 'rollout', 'status', "deployment/$deployment", '--timeout=180s')
}
Invoke-Checked 'kubectl' @('--context', $Profile, '-n', 'bookflow', 'get', 'pods,deployments,services,pvc', '-o', 'wide')
Write-Host "Deployment commands finished. Open two terminals for port forwarding:"
Write-Host "kubectl --context $Profile -n bookflow port-forward service/inventory 8001:8000"
Write-Host "kubectl --context $Profile -n bookflow port-forward service/orders 8002:8000"
Write-Host "Dashboard: minikube -p $Profile dashboard"
