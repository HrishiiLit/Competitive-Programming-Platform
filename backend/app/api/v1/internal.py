from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.judging.judge0 import Judge0Provider
from app.services.judging.service import JudgingService

router = APIRouter(prefix="/internal", tags=["Internal Webhooks"])


@router.post("/judge-callbacks", status_code=status.HTTP_200_OK)
async def judge0_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_judge0_signature: str = Header(None, alias="X-Judge0-Signature"),
):
    raw_body = await request.body()
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")

    provider = Judge0Provider()

    try:
        run = await JudgingService.handle_judge_callback(
            db=db,
            raw_body=raw_body,
            signature_header=x_judge0_signature,
            payload=payload,
            provider=provider,
        )
        return {
            "status": "success",
            "token": payload.get("token"),
            "processed": run is not None,
        }
    except ValueError as e:
        err_msg = str(e)
        if "signature" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid callback HMAC signature",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )
