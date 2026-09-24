from fastapi import HTTPException, Request


def page(query, limit: int, offset: int, serialize) -> dict:
    limit = max(1, min(limit, 500))
    total = query.order_by(None).count()
    return {"items": [serialize(r) for r in query.limit(limit).offset(max(0, offset)).all()], "total": total}


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def not_found(what: str):
    raise HTTPException(404, f"{what} not found")
