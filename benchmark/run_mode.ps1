param(
  [ValidateSet("rest","messagepack","grpc")]
  [string]$Mode = "rest"
)

$ErrorActionPreference = "Stop"
$env:INTERNAL_MODE = $Mode

docker compose down
docker compose up -d --build

if (!(Test-Path ".\benchmark\results")) {
  New-Item -ItemType Directory -Path ".\benchmark\results" | Out-Null
}

docker compose --profile bench run --rm benchmark-client
