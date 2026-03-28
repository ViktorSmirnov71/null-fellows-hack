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

@router.post("/ingest/bulk", status_code=status.HTTP_201_CREATED)
async def ingest_signals_bulk(
    signals: list[SignalIngest],
    user=Depends(require_admin)
):
    """
    Bulk ingest — AI engine posts all signals from one
    pipeline run in a single call instead of N requests.
    Max 100 signals per call.
    """
    if len(signals) > 100:
        raise HTTPException(
            status_code=400,
            detail="Max 100 signals per bulk request"
        )

    results = []
    for signal in signals:
        try:
            result = await service.ingest_signal(signal)
            results.append({"ticker": signal.ticker, "status": "ok", "id": result["id"]})
        except Exception as e:
            results.append({"ticker": signal.ticker, "status": "error", "detail": str(e)})

    return {
        "processed": len(results),
        "success": sum(1 for r in results if r["status"] == "ok"),
        "failed": sum(1 for r in results if r["status"] == "error"),
        "results": results
    }

from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.auth import get_current_user, require_admin, optional_auth
from app.services.risk_service import RiskService
from app.model.schemas import SignalIngest, BulkSignalIngest, BulkSignalResponse, BulkSignalResult

router = APIRouter()
service = RiskService()


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_signal(
    body: SignalIngest,
    user=Depends(require_admin)
):
    """
    Single signal ingest.
    Called by AI engine for individual high-priority signals
    (e.g. Claude deep analysis outputs).
    """
    return await service.ingest_signal(body)


@router.post("/ingest/bulk", status_code=status.HTTP_201_CREATED)
async def ingest_signals_bulk(
    body: BulkSignalIngest,
    user=Depends(require_admin)
):
    """
    Bulk signal ingest — primary endpoint for AI engine pipeline runs.
    AI engine POSTs all signals from one Groq → FinBERT → Claude run
    in a single call. Much more efficient than N individual requests.

    Max 200 signals per call. Source run ID is optional but useful
    for tracking which pipeline run produced which signals.
    """
    if len(body.signals) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No signals provided"
        )
    if len(body.signals) > 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Max 200 signals per bulk request — split into smaller batches"
        )

    result = await service.ingest_signals_bulk(
        body.signals,
        source_run_id=body.source_run_id
    )

    # Build structured response
    results = []
    for signal in body.signals:
        signal_id = result["inserted_ids"].get(signal.ticker)
        failed = any(e["ticker"] == signal.ticker for e in result["errors"])
        results.append(BulkSignalResult(
            ticker=signal.ticker,
            status="error" if failed else "ok",
            id=signal_id,
            detail=next(
                (e["error"] for e in result["errors"] if e["ticker"] == signal.ticker),
                None
            )
        ))

    return BulkSignalResponse(
        processed=len(body.signals),
        success=result["rows_inserted"],
        failed=len(result["errors"]),
        source_run_id=body.source_run_id,
        results=results
    )


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


@router.get("/risk")
async def get_bulk_risk_scores(
    tickers: str = Query(..., description="Comma separated e.g. AAPL,MSFT,SPY"),
    user=Depends(get_current_user)
):
    """
    Bulk risk scores for multiple tickers in one call.
    Frontend RiskDashboardPanel uses this to load the whole
    portfolio risk overlay at once.
    """
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        raise HTTPException(status_code=400, detail="No tickers provided")
    if len(ticker_list) > 50:
        raise HTTPException(status_code=400, detail="Max 50 tickers per request")

    scores = await service.get_risk_scores_bulk(ticker_list)
    return {
        ticker: score.dict() if score else None
        for ticker, score in scores.items()
    }


@router.get("/{ticker}")
async def get_signals(
    ticker: str,
    limit: int = Query(default=20, le=100),
    source: str = Query(default=None, description="Filter by source e.g. gdelt"),
    user=Depends(get_current_user)
):
    """
    Latest signals for a ticker.
    Optional source filter so frontend can show
    only geopolitical signals or only macro signals.
    """
    return await service.get_signals_for_ticker(
        ticker.upper(), limit=limit, source=source
    )


@router.get("/")
async def get_latest_signals(
    limit: int = Query(default=50, le=200),
    source: str = Query(default=None),
    user=Depends(optional_auth)
):
    """
    All recent signals across tickers — live feed panel.
    Optional source filter. No auth required for public feed.
    """
    return await service.get_latest_signals(limit=limit, source=source)