$ErrorActionPreference = "Stop"

Write-Host "REST benchmark"
docker compose up -d --build
python .\benchmark\benchmark.py

Write-Host "MessagePack benchmark"
docker compose down
$env:COMPOSE_PROFILES = ""
(Get-Content .\docker-compose.yml) | Set-Content .\docker-compose.yml.bak > $null
Write-Host "Set INTERNAL_MODE=messagepack manually in docker-compose.yml, then run:"
Write-Host "docker compose up -d --build"
Write-Host "python .\benchmark\benchmark.py"
