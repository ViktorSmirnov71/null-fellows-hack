from fastapi import APIRouter, Depends, HTTPException, status
from app.auth import get_current_user, require_admin, get_user_id
from app.services.portfolio_service import PortfolioService
from app.model.schemas import (
    PortfolioCreate, PortfolioUpdate,
    RebalancePreviewRequest, BacktestIngest
)

router = APIRouter()
service = PortfolioService()


@router.get("/")
async def list_portfolios(user=Depends(get_current_user)):
    return await service.get_user_portfolios(get_user_id(user))


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    body: PortfolioCreate,
    user=Depends(get_current_user)
):
    return await service.create(get_user_id(user), body)


@router.get("/{portfolio_id}")
async def get_portfolio(
    portfolio_id: str,
    user=Depends(get_current_user)
):
    portfolio = await service.get(portfolio_id, get_user_id(user))
    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found"
        )
    return portfolio


@router.put("/{portfolio_id}")
async def update_portfolio(
    portfolio_id: str,
    body: PortfolioUpdate,
    user=Depends(get_current_user)
):
    updated = await service.update(portfolio_id, get_user_id(user), body)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found"
        )
    return updated


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portfolio(
    portfolio_id: str,
    user=Depends(get_current_user)
):
    await service.delete(portfolio_id, get_user_id(user))


@router.post("/{portfolio_id}/preview")
async def preview_rebalance(
    portfolio_id: str,
    body: RebalancePreviewRequest,
    user=Depends(get_current_user)
):
    return await service.preview_rebalance(
        portfolio_id, get_user_id(user), body
    )


@router.post("/{portfolio_id}/backtest", status_code=status.HTTP_201_CREATED)
async def ingest_backtest(
    portfolio_id: str,
    body: BacktestIngest,
    user=Depends(require_admin)
):
    """
    Called by AI engine after bt/vectorbt run completes.
    Admin only — stores result and marks kept/discarded.
    """
    body.portfolio_id = portfolio_id
    return await service.ingest_backtest(body)


@router.get("/{portfolio_id}/backtest")
async def get_backtest_history(
    portfolio_id: str,
    user=Depends(get_current_user)
):
    """Last 20 backtest runs — for the RiskDashboardPanel."""
    return await service.get_backtest_history(portfolio_id)


@router.get("/{portfolio_id}/experiments")
async def get_experiments(
    portfolio_id: str,
    user=Depends(get_current_user)
):
    """Full experiment log — for the AutoAllocatorPanel."""
    return await service.get_experiments(portfolio_id)