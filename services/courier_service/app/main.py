import os
import threading
from concurrent import futures

import grpc
import uvicorn
from fastapi import Depends, FastAPI, Request
from pydantic import BaseModel
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String
from sqlalchemy.orm import Session, declarative_base

from shared.common.database import SessionLocal, get_db
from shared.common.msgpack_utils import msgpack_response, read_msgpack_body
from shared.generated import courier_pb2, courier_pb2_grpc


SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8002"))
GRPC_PORT = int(os.getenv("GRPC_PORT", "50052"))

Base = declarative_base()


class Courier(Base):
    __tablename__ = "couriers"
    __table_args__ = {"schema": "couriers"}

    id = Column(BigInteger, primary_key=True)
    full_name = Column(String, nullable=False)
    phone = Column(String, nullable=False)


class Delivery(Base):
    __tablename__ = "deliveries"
    __table_args__ = {"schema": "couriers"}

    id = Column(BigInteger, primary_key=True)
    order_id = Column(BigInteger, nullable=False)
    courier_id = Column(BigInteger, ForeignKey("couriers.couriers.id"), nullable=False)
    address = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)


class DeliveryCreate(BaseModel):
    order_id: int
    address: str
    status: str = "assigned"


def delivery_to_dict(delivery: Delivery | None) -> dict:
    if not delivery:
        return {}
    return {
        "id": int(delivery.id),
        "order_id": int(delivery.order_id),
        "courier_id": int(delivery.courier_id),
        "address": delivery.address,
        "status": delivery.status,
    }


def pick_courier_id(db: Session) -> int:
    courier = db.query(Courier).order_by(Courier.id.asc()).first()
    return int(courier.id) if courier else 1


def create_delivery_record(db: Session, payload: DeliveryCreate) -> Delivery:
    delivery = Delivery(
        order_id=payload.order_id,
        courier_id=pick_courier_id(db),
        address=payload.address,
        status=payload.status,
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return delivery


def get_delivery_by_order(db: Session, order_id: int) -> Delivery | None:
    return (
        db.query(Delivery)
        .filter(Delivery.order_id == order_id)
        .order_by(Delivery.id.desc())
        .first()
    )


class CourierInternalService(courier_pb2_grpc.CourierInternalServiceServicer):
    def CreateDelivery(self, request, context):
        db = SessionLocal()
        try:
            delivery = create_delivery_record(
                db,
                DeliveryCreate(order_id=request.order_id, address=request.address, status=request.status or "assigned"),
            )
            return courier_pb2.DeliveryReply(**delivery_to_dict(delivery))
        finally:
            db.close()

    def GetDeliveryByOrder(self, request, context):
        db = SessionLocal()
        try:
            delivery = get_delivery_by_order(db, request.order_id)
            return courier_pb2.DeliveryReply(**delivery_to_dict(delivery))
        finally:
            db.close()


grpc_server = None
grpc_lock = threading.Lock()


def ensure_grpc_started():
    global grpc_server
    with grpc_lock:
        if grpc_server is not None:
            return
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
        courier_pb2_grpc.add_CourierInternalServiceServicer_to_server(CourierInternalService(), server)
        server.add_insecure_port(f"[::]:{GRPC_PORT}")
        server.start()
        grpc_server = server


app = FastAPI(title="Courier Service")


@app.on_event("startup")
def startup_event():
    ensure_grpc_started()


@app.get("/health")
def health():
    return {"service": "courier-service", "status": "ok"}


@app.post("/deliveries")
def create_delivery(payload: DeliveryCreate, db: Session = Depends(get_db)):
    delivery = create_delivery_record(db, payload)
    return delivery_to_dict(delivery)


@app.get("/deliveries/order/{order_id}")
def get_delivery(order_id: int, db: Session = Depends(get_db)):
    delivery = get_delivery_by_order(db, order_id)
    return delivery_to_dict(delivery)


@app.post("/internal-msgpack/deliveries/create")
async def create_delivery_msgpack(request: Request, db: Session = Depends(get_db)):
    payload = await read_msgpack_body(request)
    delivery = create_delivery_record(db, DeliveryCreate(**payload))
    return msgpack_response(delivery_to_dict(delivery))


@app.get("/internal-msgpack/deliveries/order/{order_id}")
def get_delivery_msgpack(order_id: int, db: Session = Depends(get_db)):
    delivery = get_delivery_by_order(db, order_id)
    return msgpack_response(delivery_to_dict(delivery))


if __name__ == "__main__":
    ensure_grpc_started()
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
