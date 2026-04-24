import os
from decimal import Decimal

import grpc
import msgpack
import requests
import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Session, declarative_base

from shared.common.database import get_db
from shared.generated import (
    courier_pb2,
    courier_pb2_grpc,
    notification_pb2,
    notification_pb2_grpc,
    payment_pb2,
    payment_pb2_grpc,
)


SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8004"))
INTERNAL_MODE = os.getenv("INTERNAL_MODE", "rest").lower()

PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://localhost:8001")
COURIER_SERVICE_URL = os.getenv("COURIER_SERVICE_URL", "http://localhost:8002")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8003")

PAYMENT_GRPC_TARGET = os.getenv("PAYMENT_GRPC_TARGET", "localhost:50051")
COURIER_GRPC_TARGET = os.getenv("COURIER_GRPC_TARGET", "localhost:50052")
NOTIFICATION_GRPC_TARGET = os.getenv("NOTIFICATION_GRPC_TARGET", "localhost:50053")

Base = declarative_base()


class Product(Base):
    __tablename__ = "products"
    __table_args__ = {"schema": "products"}

    id = Column(BigInteger, primary_key=True)
    category_id = Column(BigInteger, nullable=False)
    name = Column(String, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = {"schema": "products"}

    id = Column(BigInteger, primary_key=True)
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = {"schema": "products"}

    id = Column(BigInteger, primary_key=True)
    customer_id = Column(BigInteger, nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = {"schema": "products"}

    id = Column(BigInteger, primary_key=True)
    order_id = Column(BigInteger, ForeignKey("products.orders.id"), nullable=False)
    product_id = Column(BigInteger, nullable=False)
    quantity = Column(BigInteger, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)


class CreateOrderRequest(BaseModel):
    customer_id: int
    product_ids: list[int]


class CheckoutRequest(CreateOrderRequest):
    delivery_address: str = "Simple address, 1"
    note: str = ""


def product_to_dict(product: Product) -> dict:
    return {
        "id": int(product.id),
        "category_id": int(product.category_id),
        "name": product.name,
        "price": float(product.price),
    }


def order_to_dict(order: Order) -> dict:
    return {
        "id": int(order.id),
        "customer_id": int(order.customer_id),
        "total_amount": float(order.total_amount),
        "status": order.status,
    }


def get_products_by_ids(db: Session, product_ids: list[int]) -> list[Product]:
    return db.query(Product).filter(Product.id.in_(product_ids)).all()


def get_customer(db: Session, customer_id: int) -> Customer | None:
    return db.query(Customer).filter(Customer.id == customer_id).first()


def create_order_record(db: Session, payload: CreateOrderRequest) -> tuple[Order, list[Product]]:
    customer = get_customer(db, payload.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    products = get_products_by_ids(db, payload.product_ids)
    if not products:
        raise HTTPException(status_code=404, detail="Products not found")

    total = sum(Decimal(product.price) for product in products)

    order = Order(customer_id=payload.customer_id, total_amount=total, status="created")
    db.add(order)
    db.commit()
    db.refresh(order)

    for product in products:
        item = OrderItem(order_id=order.id, product_id=product.id, quantity=1, price=product.price)
        db.add(item)

    db.commit()
    db.refresh(order)
    return order, products


def create_payment(order_id: int, amount: float) -> dict:
    payload = {"order_id": order_id, "amount": amount, "status": "paid"}

    if INTERNAL_MODE == "messagepack":
        response = requests.post(
            f"{PAYMENT_SERVICE_URL}/internal-msgpack/payments/create",
            data=msgpack.packb(payload, use_bin_type=True),
            headers={"Content-Type": "application/msgpack"},
            timeout=10,
        )
        response.raise_for_status()
        return msgpack.unpackb(response.content, raw=False)

    if INTERNAL_MODE == "grpc":
        with grpc.insecure_channel(PAYMENT_GRPC_TARGET) as channel:
            stub = payment_pb2_grpc.PaymentInternalServiceStub(channel)
            reply = stub.CreatePayment(payment_pb2.CreatePaymentRequest(**payload))
            return {
                "id": reply.id,
                "order_id": reply.order_id,
                "amount": reply.amount,
                "status": reply.status,
            }

    response = requests.post(f"{PAYMENT_SERVICE_URL}/payments", json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def create_delivery(order_id: int, address: str) -> dict:
    payload = {"order_id": order_id, "address": address, "status": "assigned"}

    if INTERNAL_MODE == "messagepack":
        response = requests.post(
            f"{COURIER_SERVICE_URL}/internal-msgpack/deliveries/create",
            data=msgpack.packb(payload, use_bin_type=True),
            headers={"Content-Type": "application/msgpack"},
            timeout=10,
        )
        response.raise_for_status()
        return msgpack.unpackb(response.content, raw=False)

    if INTERNAL_MODE == "grpc":
        with grpc.insecure_channel(COURIER_GRPC_TARGET) as channel:
            stub = courier_pb2_grpc.CourierInternalServiceStub(channel)
            reply = stub.CreateDelivery(courier_pb2.CreateDeliveryRequest(**payload))
            return {
                "id": reply.id,
                "order_id": reply.order_id,
                "courier_id": reply.courier_id,
                "address": reply.address,
                "status": reply.status,
            }

    response = requests.post(f"{COURIER_SERVICE_URL}/deliveries", json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def create_notification(order_id: int, message: str) -> dict:
    payload = {"order_id": order_id, "channel": "email", "message": message, "status": "sent"}

    if INTERNAL_MODE == "messagepack":
        response = requests.post(
            f"{NOTIFICATION_SERVICE_URL}/internal-msgpack/notifications/create",
            data=msgpack.packb(payload, use_bin_type=True),
            headers={"Content-Type": "application/msgpack"},
            timeout=10,
        )
        response.raise_for_status()
        return msgpack.unpackb(response.content, raw=False)

    if INTERNAL_MODE == "grpc":
        with grpc.insecure_channel(NOTIFICATION_GRPC_TARGET) as channel:
            stub = notification_pb2_grpc.NotificationInternalServiceStub(channel)
            reply = stub.CreateNotification(notification_pb2.CreateNotificationRequest(**payload))
            return {
                "id": reply.id,
                "order_id": reply.order_id,
                "channel": reply.channel,
                "message": reply.message,
                "status": reply.status,
            }

    response = requests.post(f"{NOTIFICATION_SERVICE_URL}/notifications", json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


app = FastAPI(title="Product Service")


@app.get("/health")
def health():
    return {"service": "product-service", "status": "ok", "internal_mode": INTERNAL_MODE}


@app.get("/products")
def list_products(limit: int = 20, db: Session = Depends(get_db)):
    products = db.query(Product).order_by(Product.id.asc()).limit(limit).all()
    return [product_to_dict(product) for product in products]


@app.post("/orders")
def create_order(payload: CreateOrderRequest, db: Session = Depends(get_db)):
    order, products = create_order_record(db, payload)
    return {
        "order": order_to_dict(order),
        "products": [product_to_dict(product) for product in products],
    }


@app.post("/orders/checkout")
def checkout(payload: CheckoutRequest, db: Session = Depends(get_db)):
    try:
        order, products = create_order_record(db, payload)
        payment = create_payment(order.id, float(order.total_amount))
        delivery = create_delivery(order.id, payload.delivery_address)
        notification = create_notification(order.id, f"Order {order.id} created. {payload.note}".strip())

        order.status = "completed"
        db.add(order)
        db.commit()
        db.refresh(order)

        return {
            "internal_mode": INTERNAL_MODE,
            "order": order_to_dict(order),
            "products": [product_to_dict(product) for product in products],
            "payment": payment,
            "delivery": delivery,
            "notification": notification,
        }
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Internal HTTP call failed: {exc}") from exc
    except grpc.RpcError as exc:
        raise HTTPException(status_code=502, detail=f"Internal gRPC call failed: {exc}") from exc


@app.get("/orders/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    product_ids = [int(item.product_id) for item in items]
    products = get_products_by_ids(db, product_ids)

    return {
        "order": order_to_dict(order),
        "products": [product_to_dict(product) for product in products],
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
