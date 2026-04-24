import os
import threading
from concurrent import futures

import grpc
import uvicorn
from fastapi import Depends, FastAPI, Request
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Numeric, String, BigInteger
from sqlalchemy.orm import Session, declarative_base

from shared.common.database import SessionLocal, get_db
from shared.common.msgpack_utils import msgpack_response, read_msgpack_body
from shared.generated import payment_pb2, payment_pb2_grpc


SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8001"))
GRPC_PORT = int(os.getenv("GRPC_PORT", "50051"))

Base = declarative_base()


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = {"schema": "payments"}

    id = Column(BigInteger, primary_key=True)
    order_id = Column(BigInteger, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)


class PaymentCreate(BaseModel):
    order_id: int
    amount: float
    status: str = "paid"


def payment_to_dict(payment: Payment | None) -> dict:
    if not payment:
        return {}
    return {
        "id": int(payment.id),
        "order_id": int(payment.order_id),
        "amount": float(payment.amount),
        "status": payment.status,
    }


def create_payment_record(db: Session, payload: PaymentCreate) -> Payment:
    payment = Payment(order_id=payload.order_id, amount=payload.amount, status=payload.status)
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def get_payment_by_order(db: Session, order_id: int) -> Payment | None:
    return (
        db.query(Payment)
        .filter(Payment.order_id == order_id)
        .order_by(Payment.id.desc())
        .first()
    )


class PaymentInternalService(payment_pb2_grpc.PaymentInternalServiceServicer):
    def CreatePayment(self, request, context):
        db = SessionLocal()
        try:
            payment = create_payment_record(
                db,
                PaymentCreate(order_id=request.order_id, amount=request.amount, status=request.status or "paid"),
            )
            return payment_pb2.PaymentReply(**payment_to_dict(payment))
        finally:
            db.close()

    def GetPaymentByOrder(self, request, context):
        db = SessionLocal()
        try:
            payment = get_payment_by_order(db, request.order_id)
            return payment_pb2.PaymentReply(**payment_to_dict(payment))
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
        payment_pb2_grpc.add_PaymentInternalServiceServicer_to_server(PaymentInternalService(), server)
        server.add_insecure_port(f"[::]:{GRPC_PORT}")
        server.start()
        grpc_server = server


app = FastAPI(title="Payment Service")


@app.on_event("startup")
def startup_event():
    ensure_grpc_started()


@app.get("/health")
def health():
    return {"service": "payment-service", "status": "ok"}


@app.post("/payments")
def create_payment(payload: PaymentCreate, db: Session = Depends(get_db)):
    payment = create_payment_record(db, payload)
    return payment_to_dict(payment)


@app.get("/payments/order/{order_id}")
def get_payment(order_id: int, db: Session = Depends(get_db)):
    payment = get_payment_by_order(db, order_id)
    return payment_to_dict(payment)


@app.post("/internal-msgpack/payments/create")
async def create_payment_msgpack(request: Request, db: Session = Depends(get_db)):
    payload = await read_msgpack_body(request)
    payment = create_payment_record(db, PaymentCreate(**payload))
    return msgpack_response(payment_to_dict(payment))


@app.get("/internal-msgpack/payments/order/{order_id}")
def get_payment_msgpack(order_id: int, db: Session = Depends(get_db)):
    payment = get_payment_by_order(db, order_id)
    return msgpack_response(payment_to_dict(payment))


if __name__ == "__main__":
    ensure_grpc_started()
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
