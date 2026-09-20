from datetime import datetime, timezone
import os
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field


app = FastAPI(
    title="NEXUS AI E-Agent API",
    version="0.2.0",
    description="Safety-first trading infrastructure. Live order execution remains disabled.",
)


class RiskLimits(BaseModel):
    max_position_notional_usd: float = Field(default=25.0, gt=0, le=100000)
    max_daily_loss_usd: float = Field(default=5.0, gt=0, le=100000)
    max_open_positions: int = Field(default=1, ge=0, le=100)
    require_manual_approval: bool = True


def trading_mode() -> str:
    return os.getenv("TRADING_MODE", "disabled").strip().lower()


def binance_environment() -> str:
    return os.getenv("BINANCE_ENV", "testnet").strip().lower()


def safety_state() -> dict[str, Any]:
    mode = trading_mode()
    return {
        "trading_mode": mode,
        "binance_environment": binance_environment(),
        "live_orders_enabled": False,
        "withdrawals_enabled": False,
        "manual_approval_required": True,
        "kill_switch": True,
        "status": "safe" if mode == "disabled" else "restricted",
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "nexus-api",
        "version": app.version,
        "trading_mode": trading_mode(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/status")
def status() -> dict[str, Any]:
    return {
        "service": "nexus-api",
        "version": app.version,
        "environment": binance_environment(),
        "trading_mode": trading_mode(),
        "live_orders_enabled": False,
        "safety": safety_state(),
    }


@app.get("/api/v1/safety")
def safety() -> dict[str, Any]:
    """Expose the current safety posture without revealing secrets."""
    return safety_state()


@app.get("/api/v1/risk/limits", response_model=RiskLimits)
def get_risk_limits() -> RiskLimits:
    """Return conservative default risk limits for the protected execution layer."""
    return RiskLimits()


@app.get("/api/v1/market/supported")
def supported_market_features() -> dict[str, Any]:
    """Declare implemented market capabilities without placing orders or using credentials."""
    return {
        "public_market_data_adapter": "planned",
        "spot": {"enabled": False, "order_execution": False},
        "futures": {"enabled": False, "order_execution": False},
        "analysis": {"enabled": False, "signal_generation": False},
        "reason": "Safety gate remains closed until validation and monitoring are complete.",
    }


@app.get("/api/v1/ready")
def readiness() -> dict[str, Any]:
    return {
        "ready": True,
        "service": "nexus-api",
        "checks": {
            "api_process": "ok",
            "configuration_defaults": "ok",
            "live_order_gate": "closed",
            "secret_exposure": "not_used",
        },
    }
