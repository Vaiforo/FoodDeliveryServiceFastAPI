# FoodDeliveryServiceFastAPI

Минимальный учебный проект по теме **«Доставка еды»**.

В проекте есть 5 микросервисов:

- `gateway-service`
- `product-service`
- `payment-service`
- `courier-service`
- `notification-service`

Также есть:
- PostgreSQL в Docker
- автоматическое создание схем и данных
- не менее 100 записей в каждой таблице
- REST API для внешних вызовов
- MessagePack для внутренних вызовов
- gRPC для внутренних вызовов
- benchmark-клиент для 100 запусков
- сохранение результатов в CSV / JSON / PNG

---

## 1. Стек

- Python 3.12
- FastAPI
- SQLAlchemy
- PostgreSQL
- Docker / Docker Compose
- requests
- msgpack
- grpcio

---

## 2. Структура

```text
FoodDeliveryServiceFastAPI/
├─ benchmark/
├─ db/
├─ docs/
├─ proto/
├─ services/
├─ shared/
├─ docker-compose.yml
├─ requirements.txt
└─ README.md
```

---

## 3. Быстрый запуск

### Windows 11 / PowerShell
```powershell
docker compose up -d --build
```

После этого сервисы будут доступны:

- gateway: `http://localhost:8000`
- payment: `http://localhost:8001`
- courier: `http://localhost:8002`
- notification: `http://localhost:8003`
- product: `http://localhost:8004`

Swagger:
- `http://localhost:8000/docs`
- `http://localhost:8001/docs`
- `http://localhost:8002/docs`
- `http://localhost:8003/docs`
- `http://localhost:8004/docs`

---

## 4. Полезный тестовый запрос

```http
POST http://localhost:8000/api/orders/checkout
Content-Type: application/json

{
  "customer_id": 1,
  "product_ids": [1, 2, 3],
  "delivery_address": "Moscow, Test street 1",
  "note": "test"
}
```

---

## 5. Переключение внутреннего транспорта

В `docker-compose.yml` уже есть строка:

```yaml
INTERNAL_MODE: ${INTERNAL_MODE:-rest}
```

### REST
```powershell
$env:INTERNAL_MODE="rest"
docker compose up -d --build
```

### MessagePack
```powershell
$env:INTERNAL_MODE="messagepack"
docker compose up -d --build
```

### gRPC
```powershell
$env:INTERNAL_MODE="grpc"
docker compose up -d --build
```

---

## 6. Benchmark

Есть готовый клиент:
- `benchmark/benchmark.py`

Есть готовый PowerShell-скрипт:
- `benchmark/run_mode.ps1`

Примеры:

```powershell
.enchmarkun_mode.ps1 rest
.enchmarkun_mode.ps1 messagepack
.enchmarkun_mode.ps1 grpc
```

Результаты будут сохранены в:
- `benchmark/results/rest_sample.csv`
- `benchmark/results/rest_stats.json`
- `benchmark/results/rest_plot.png`

И аналогично для остальных режимов.

---

## 7. Где смотреть архитектуру

- `docs/architecture.md`
- `docs/benchmark_steps.md`

---

## 8. Важно

Это специально сделано **максимально просто**:

- одна БД;
- минимум бизнес-логики;
- сервисы оплаты / курьеров / уведомлений очень простые;
- gateway только проксирует;
- product-service оркестрирует сценарий;
- без миграций, брокеров и лишней инфраструктуры.

Для учебного задания и запуска с Windows 11 этого обычно достаточно.
