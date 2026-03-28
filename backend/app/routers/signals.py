from fastapi import APIRouter, Depends, HTTPException, status
from app.auth import get_current_user, require_admin
from app.services.risk_service import RiskService
from app.model.schemas import SignalIngest

router = APIRouter()
service = RiskService()


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_signal(
    body: SignalIngest,
    user=Depends(require_admin)
):
    """
    Called by the AI engine after Groq → FinBERT → Claude pipeline.
    Admin only — your AI team's service account needs admin role.
    """
    return await service.ingest_signal(body)


@router.get("/risk/{ticker}")
async def get_risk_score(
    ticker: str,
    user=Depends(get_current_user)
):
    """Composite risk score for a ticker — used by RiskDashboardPanel."""
    score = await service.get_risk_score(ticker.upper())
    if not score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No signals found for {ticker}"
        )
    return score


@router.get("/{ticker}")
async def get_signals(
    ticker: str,
    limit: int = 20,
    user=Depends(get_current_user)
):
    """Latest signals for a ticker — used by frontend signal feed."""
    return await service.get_signals_for_ticker(ticker.upper(), limit)


@router.get("/")
async def get_latest_signals(
    limit: int = 50,
    user=Depends(get_current_user)
):
    """All recent signals across tickers — for the live feed panel."""
    return await service.get_latest_signals(limit)