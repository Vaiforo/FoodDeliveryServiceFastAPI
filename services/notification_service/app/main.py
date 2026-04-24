import os
import threading
from concurrent import futures

import grpc
import uvicorn
from fastapi import Depends, FastAPI, Request
from pydantic import BaseModel
from sqlalchemy import BigInteger, Column, DateTime, String
from sqlalchemy.orm import Session, declarative_base

from shared.common.database import SessionLocal, get_db
from shared.common.msgpack_utils import msgpack_response, read_msgpack_body
from shared.generated import notification_pb2, notification_pb2_grpc


SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8003"))
GRPC_PORT = int(os.getenv("GRPC_PORT", "50053"))

Base = declarative_base()


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = {"schema": "notifications"}

    id = Column(BigInteger, primary_key=True)
    order_id = Column(BigInteger, nullable=False)
    channel = Column(String, nullable=False)
    message = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)


class NotificationCreate(BaseModel):
    order_id: int
    channel: str = "email"
    message: str
    status: str = "sent"


def notification_to_dict(item: Notification | None) -> dict:
    if not item:
        return {}
    return {
        "id": int(item.id),
        "order_id": int(item.order_id),
        "channel": item.channel,
        "message": item.message,
        "status": item.status,
    }


def create_notification_record(db: Session, payload: NotificationCreate) -> Notification:
    item = Notification(
        order_id=payload.order_id,
        channel=payload.channel,
        message=payload.message,
        status=payload.status,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_notification_by_order(db: Session, order_id: int) -> Notification | None:
    return (
        db.query(Notification)
        .filter(Notification.order_id == order_id)
        .order_by(Notification.id.desc())
        .first()
    )


class NotificationInternalService(notification_pb2_grpc.NotificationInternalServiceServicer):
    def CreateNotification(self, request, context):
        db = SessionLocal()
        try:
            item = create_notification_record(
                db,
                NotificationCreate(
                    order_id=request.order_id,
                    channel=request.channel or "email",
                    message=request.message,
                    status=request.status or "sent",
                ),
            )
            return notification_pb2.NotificationReply(**notification_to_dict(item))
        finally:
            db.close()

    def GetNotificationByOrder(self, request, context):
        db = SessionLocal()
        try:
            item = get_notification_by_order(db, request.order_id)
            return notification_pb2.NotificationReply(**notification_to_dict(item))
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
        notification_pb2_grpc.add_NotificationInternalServiceServicer_to_server(NotificationInternalService(), server)
        server.add_insecure_port(f"[::]:{GRPC_PORT}")
        server.start()
        grpc_server = server


app = FastAPI(title="Notification Service")


@app.on_event("startup")
def startup_event():
    ensure_grpc_started()


@app.get("/health")
def health():
    return {"service": "notification-service", "status": "ok"}


@app.post("/notifications")
def create_notification(payload: NotificationCreate, db: Session = Depends(get_db)):
    item = create_notification_record(db, payload)
    return notification_to_dict(item)


@app.get("/notifications/order/{order_id}")
def get_notification(order_id: int, db: Session = Depends(get_db)):
    item = get_notification_by_order(db, order_id)
    return notification_to_dict(item)


@app.post("/internal-msgpack/notifications/create")
async def create_notification_msgpack(request: Request, db: Session = Depends(get_db)):
    payload = await read_msgpack_body(request)
    item = create_notification_record(db, NotificationCreate(**payload))
    return msgpack_response(notification_to_dict(item))


@app.get("/internal-msgpack/notifications/order/{order_id}")
def get_notification_msgpack(order_id: int, db: Session = Depends(get_db)):
    item = get_notification_by_order(db, order_id)
    return msgpack_response(notification_to_dict(item))


if __name__ == "__main__":
    ensure_grpc_started()
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
