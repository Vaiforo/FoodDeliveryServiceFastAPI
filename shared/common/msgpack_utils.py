from fastapi import HTTPException, Request, Response
import msgpack


def msgpack_response(payload: dict, status_code: int = 200) -> Response:
    return Response(
        content=msgpack.packb(payload, use_bin_type=True),
        media_type="application/msgpack",
        status_code=status_code,
    )


async def read_msgpack_body(request: Request) -> dict:
    raw = await request.body()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty MessagePack body")
    return msgpack.unpackb(raw, raw=False)
