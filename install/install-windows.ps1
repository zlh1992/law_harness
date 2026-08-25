param(
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
  [string]$MacBaseUrl = "http://127.0.0.1:4010/v1"
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
$settings = Get-Content (Join-Path $ProjectRoot "config\dsh-settings.yaml") -Raw
$settings = $settings -replace "http://127\.0\.0\.1:4010/v1", $MacBaseUrl
Set-Content -Path (Join-Path $dshHome "settings.yaml") -Value $settings -Encoding utf8
$env:DSH_HOME = $dshHome

if (-not (Get-Command dsh -ErrorAction SilentlyContinue)) {
  npm install --global @deepseek-ai/dsh@0.1.0-rc.7
}
Write-Host "Harness 安装完成。请设置 `$env:DSH_PROXY_TOKEN 为 Mac 网关 Token。" -ForegroundColor Green
Write-Host "启动：dsh web（当前 PowerShell）"
