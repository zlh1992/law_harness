param(
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
  [string]$Ds4ApiKey = "local"
)

$ErrorActionPreference = "Stop"
Write-Host "== Desktop Law Harness / Windows setup ==" -ForegroundColor Cyan
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install --id OpenJS.NodeJS.LTS --exact --source winget
  } else {
    throw "未找到 Node.js 或 winget，请先安装 Node.js >=20。"
  }
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "npm 不在 PATH 中，请重启 PowerShell 后重试。" }

$dshHome = Join-Path $ProjectRoot ".dsh-home"
New-Item -ItemType Directory -Force -Path $dshHome | Out-Null
Copy-Item (Join-Path $ProjectRoot "config\dsh-settings.yaml") (Join-Path $dshHome "settings.yaml") -Force
$credentialPath = Join-Path $dshHome ".credentials.yaml"
Set-Content -Path $credentialPath -Value "DS4_API_KEY: $Ds4ApiKey" -Encoding utf8
$env:DSH_HOME = $dshHome
$env:DS4_API_KEY = $Ds4ApiKey

if (-not (Get-Command dsh -ErrorAction SilentlyContinue)) {
  npm install --global @deepseek-ai/dsh@0.1.0-rc.7
}
Write-Host "Harness 安装完成，模型请求将直连本机 DS4F deepseek-v4-flash。" -ForegroundColor Green
Write-Host "启动：dsh web（当前 PowerShell）"
