import os

import requests
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8000"))
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://localhost:8004")


class CheckoutRequest(BaseModel):
    customer_id: int
    product_ids: list[int]
    delivery_address: str = "Simple address, 1"
    note: str = ""


app = FastAPI(title="Gateway Service")


@app.get("/health")
def health():
    return {"service": "gateway-service", "status": "ok"}


@app.get("/api/products")
def products(limit: int = 20):
    response = requests.get(f"{PRODUCT_SERVICE_URL}/products", params={"limit": limit}, timeout=10)
    response.raise_for_status()
    return response.json()


@app.get("/api/orders/{order_id}")
def get_order(order_id: int):
    response = requests.get(f"{PRODUCT_SERVICE_URL}/orders/{order_id}", timeout=10)
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="Order not found")
    response.raise_for_status()
    return response.json()


@app.post("/api/orders/checkout")
def checkout(payload: CheckoutRequest):
    try:
        response = requests.post(
            f"{PRODUCT_SERVICE_URL}/orders/checkout",
            json=payload.model_dump(),
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Gateway proxy error: {exc}") from exc


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
