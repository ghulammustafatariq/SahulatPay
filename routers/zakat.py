"""Zakat router — live rates, calculate, pay, history. PROMPT 13."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import aiohttp
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from limiter import limiter
from models.other import ZakatCalculation
from models.user import User
from models.wallet import Wallet
from models.transaction import Transaction
from services.auth_service import get_current_user
from services.wallet_service import generate_reference
from services.notification_service import send_notification

router = APIRouter()

# ── Zakat constants ────────────────────────────────────────────────────────────
# Nisab thresholds (Islamic standard)
NISAB_GOLD_GRAMS   = Decimal("87.48")   # 7.5 tola
NISAB_SILVER_GRAMS = Decimal("612.36")  # 52.5 tola
ZAKAT_RATE         = Decimal("0.025")   # 2.5%


def _utcnow():
    return datetime.now(timezone.utc)


# ══════════════════════════════════════════════════════════════════════════════
# GET /zakat/live-rates
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/live-rates")
async def live_rates(current_user: User = Depends(get_current_user)):
    """
    Fetch live gold/silver prices from metals.live (USD/troy oz) +
    USD→PKR rate from er-api.com. No caching — always fresh.
    """
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            # metals.live — free metals API
            metals_url = "https://api.metals.live/v1/spot/gold,silver"
            async with session.get(metals_url) as resp:
                metals_data = await resp.json()

            # er-api.com — free exchange rates
            fx_url = "https://open.er-api.com/v6/latest/USD"
            async with session.get(fx_url) as resp:
                fx_data = await resp.json()

    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Could not fetch live rates: {str(e)}")

    # metals.live returns [{metal:"gold", price:USD/oz}, ...]
    gold_usd_oz   = Decimal("0")
    silver_usd_oz = Decimal("0")
    for item in metals_data:
        if item.get("metal") == "gold":
            gold_usd_oz   = Decimal(str(item.get("price", 0)))
        elif item.get("metal") == "silver":
            silver_usd_oz = Decimal(str(item.get("price", 0)))

    usd_pkr = Decimal(str(fx_data.get("rates", {}).get("PKR", 280)))

    # Convert to PKR per gram (1 troy oz = 31.1035 g)
    TROY_OZ_GRAMS    = Decimal("31.1035")
    gold_pkr_gram    = (gold_usd_oz   * usd_pkr) / TROY_OZ_GRAMS
    silver_pkr_gram  = (silver_usd_oz * usd_pkr) / TROY_OZ_GRAMS

    # Nisab values
    nisab_gold_pkr   = gold_pkr_gram   * NISAB_GOLD_GRAMS
    nisab_silver_pkr = silver_pkr_gram * NISAB_SILVER_GRAMS

    return {
        "gold_usd_per_oz":      float(round(gold_usd_oz,   2)),
        "silver_usd_per_oz":    float(round(silver_usd_oz, 4)),
        "usd_to_pkr":           float(round(usd_pkr,       2)),
        "gold_pkr_per_gram":    float(round(gold_pkr_gram,   2)),
        "silver_pkr_per_gram":  float(round(silver_pkr_gram, 4)),
        "nisab_gold_pkr":       float(round(nisab_gold_pkr,   2)),
        "nisab_silver_pkr":     float(round(nisab_silver_pkr, 2)),
        "nisab_threshold_pkr":  float(round(min(nisab_gold_pkr, nisab_silver_pkr), 2)),
        "note":                 "Nisab is the lower of gold (87.48g) or silver (612.36g) nisab.",
    }


# ══════════════════════════════════════════════════════════════════════════════
# POST /zakat/calculate
# ══════════════════════════════════════════════════════════════════════════════
class ZakatCalculateRequest(BaseModel):
    cash_pkr:               Decimal = Field(default=Decimal("0"), ge=0)
    gold_grams:             Decimal = Field(default=Decimal("0"), ge=0)
    silver_grams:           Decimal = Field(default=Decimal("0"), ge=0)
    business_inventory_pkr: Decimal = Field(default=Decimal("0"), ge=0)
    receivables_pkr:        Decimal = Field(default=Decimal("0"), ge=0)


@router.post("/calculate", status_code=201)
@limiter.limit("20/hour")
async def calculate_zakat(
    request: Request,
    body: ZakatCalculateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Calculate nisab, total assets, and zakat_due. Saves the record."""
    # Fetch live rates
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            metals_url = "https://api.metals.live/v1/spot/gold,silver"
            async with session.get(metals_url) as resp:
                metals_data = await resp.json()
            fx_url = "https://open.er-api.com/v6/latest/USD"
            async with session.get(fx_url) as resp:
                fx_data = await resp.json()
    except Exception:
        # Fallback to approximate rates if API unreachable
        metals_data = [{"metal": "gold", "price": 2300}, {"metal": "silver", "price": 27}]
        fx_data     = {"rates": {"PKR": 280}}

    gold_usd_oz   = Decimal("0")
    silver_usd_oz = Decimal("0")
    for item in metals_data:
        if item.get("metal") == "gold":
            gold_usd_oz   = Decimal(str(item.get("price", 0)))
        elif item.get("metal") == "silver":
            silver_usd_oz = Decimal(str(item.get("price", 0)))

    usd_pkr          = Decimal(str(fx_data.get("rates", {}).get("PKR", 280)))
    TROY_OZ_GRAMS    = Decimal("31.1035")
    gold_pkr_gram    = (gold_usd_oz   * usd_pkr) / TROY_OZ_GRAMS
    silver_pkr_gram  = (silver_usd_oz * usd_pkr) / TROY_OZ_GRAMS

    nisab_gold_pkr   = gold_pkr_gram   * NISAB_GOLD_GRAMS
    nisab_silver_pkr = silver_pkr_gram * NISAB_SILVER_GRAMS
    nisab_threshold  = min(nisab_gold_pkr, nisab_silver_pkr)

    gold_value_pkr   = body.gold_grams   * gold_pkr_gram
    silver_value_pkr = body.silver_grams * silver_pkr_gram

    total_assets = (
        body.cash_pkr
        + gold_value_pkr
        + silver_value_pkr
        + body.business_inventory_pkr
        + body.receivables_pkr
    )

    zakat_due = Decimal("0")
    if total_assets >= nisab_threshold:
        zakat_due = (total_assets * ZAKAT_RATE).quantize(Decimal("0.01"))

    record = ZakatCalculation(
        user_id                = current_user.id,
        cash_pkr               = body.cash_pkr,
        gold_grams             = body.gold_grams,
        silver_grams           = body.silver_grams,
        business_inventory_pkr = body.business_inventory_pkr,
        receivables_pkr        = body.receivables_pkr,
        gold_rate_per_gram     = gold_pkr_gram.quantize(Decimal("0.01")),
        silver_rate_per_gram   = silver_pkr_gram.quantize(Decimal("0.0001")),
        usd_to_pkr_rate        = usd_pkr.quantize(Decimal("0.0001")),
        total_assets_pkr       = total_assets.quantize(Decimal("0.01")),
        nisab_threshold_pkr    = nisab_threshold.quantize(Decimal("0.01")),
        zakat_due_pkr          = zakat_due,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return {
        "calculation_id":       record.id,
        "total_assets_pkr":     float(total_assets.quantize(Decimal("0.01"))),
        "nisab_threshold_pkr":  float(nisab_threshold.quantize(Decimal("0.01"))),
        "zakat_due_pkr":        float(zakat_due),
        "zakat_obligatory":     total_assets >= nisab_threshold,
        "gold_rate_per_gram":   float(gold_pkr_gram.quantize(Decimal("0.01"))),
        "silver_rate_per_gram": float(silver_pkr_gram.quantize(Decimal("0.0001"))),
        "usd_to_pkr":           float(usd_pkr),
        "breakdown": {
            "cash_pkr":               float(body.cash_pkr),
            "gold_value_pkr":         float(gold_value_pkr.quantize(Decimal("0.01"))),
            "silver_value_pkr":       float(silver_value_pkr.quantize(Decimal("0.01"))),
            "business_inventory_pkr": float(body.business_inventory_pkr),
            "receivables_pkr":        float(body.receivables_pkr),
        },
        "message": (
            f"Zakat obligatory: PKR {zakat_due:,.2f} due."
            if total_assets >= nisab_threshold
            else "Your assets are below the nisab threshold. Zakat is not obligatory."
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
# POST /zakat/pay
# ══════════════════════════════════════════════════════════════════════════════
class ZakatPayRequest(BaseModel):
    calculation_id: UUID
    pin:            str = Field(..., min_length=4, max_length=6)


@router.post("/pay", status_code=201)
@limiter.limit("5/hour")
async def pay_zakat(
    request: Request,
    body: ZakatPayRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deduct zakat_due from wallet, mark calculation as paid."""
    calc = (await db.execute(
        select(ZakatCalculation).where(
            ZakatCalculation.id      == body.calculation_id,
            ZakatCalculation.user_id == current_user.id,
        )
    )).scalar_one_or_none()

    if not calc:
        raise HTTPException(404, "Zakat calculation not found.")
    if calc.is_paid:
        raise HTTPException(400, "This zakat has already been paid.")
    if not calc.zakat_due_pkr or calc.zakat_due_pkr <= 0:
        raise HTTPException(400, "No zakat due on this calculation.")

    # Verify PIN
    import bcrypt
    if not current_user.pin_hash:
        raise HTTPException(400, "PIN not set. Please set a PIN first.")
    if not bcrypt.checkpw(body.pin.encode(), current_user.pin_hash.encode()):
        raise HTTPException(401, "Incorrect PIN.")

    # Deduct from wallet
    wallet = (await db.execute(
        select(Wallet).where(Wallet.user_id == current_user.id)
    )).scalar_one_or_none()
    if not wallet:
        raise HTTPException(404, "Wallet not found.")
    if wallet.is_frozen:
        raise HTTPException(403, "Wallet is frozen. Contact support.")
    if wallet.balance < calc.zakat_due_pkr:
        raise HTTPException(400, f"Insufficient balance. Need PKR {calc.zakat_due_pkr:,.2f}, have PKR {wallet.balance:,.2f}.")

    wallet.balance -= calc.zakat_due_pkr
    ref = generate_reference()
    txn = Transaction(
        reference_number = ref,
        type             = "zakat",
        amount           = calc.zakat_due_pkr,
        fee              = Decimal("0"),
        status           = "completed",
        sender_id        = current_user.id,
        purpose          = "Zakat",
        description      = f"Zakat payment — calculation {calc.id}",
        completed_at     = _utcnow(),
        tx_metadata      = {"calculation_id": str(calc.id)},
    )
    db.add(txn)

    calc.is_paid = True
    calc.paid_at = _utcnow()
    await db.commit()
    await db.refresh(wallet)

    # Push notification (non-blocking)
    await send_notification(
        db, current_user.id,
        title = "Zakat Paid ✅",
        body  = f"PKR {calc.zakat_due_pkr:,.2f} zakat paid successfully. JazakAllah Khair.",
        type  = "zakat",
        data  = {"calculation_id": str(calc.id), "reference": ref},
    )

    return {
        "status":          "paid",
        "zakat_paid_pkr":  float(calc.zakat_due_pkr),
        "reference_number": ref,
        "new_balance":     float(wallet.balance),
        "message":         f"PKR {calc.zakat_due_pkr:,.2f} zakat paid. JazakAllah Khair.",
    }


# ══════════════════════════════════════════════════════════════════════════════
# GET /zakat/history
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/history")
async def zakat_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all zakat calculations for the current user, newest first."""
    result = await db.execute(
        select(ZakatCalculation)
        .where(ZakatCalculation.user_id == current_user.id)
        .order_by(ZakatCalculation.created_at.desc())
    )
    records = result.scalars().all()

    return {
        "count": len(records),
        "calculations": [
            {
                "id":                    r.id,
                "total_assets_pkr":      float(r.total_assets_pkr or 0),
                "nisab_threshold_pkr":   float(r.nisab_threshold_pkr or 0),
                "zakat_due_pkr":         float(r.zakat_due_pkr or 0),
                "is_paid":               r.is_paid,
                "paid_at":               r.paid_at.isoformat() if r.paid_at else None,
                "gold_rate_per_gram":    float(r.gold_rate_per_gram or 0),
                "silver_rate_per_gram":  float(r.silver_rate_per_gram or 0),
                "usd_to_pkr_rate":       float(r.usd_to_pkr_rate or 0),
                "breakdown": {
                    "cash_pkr":               float(r.cash_pkr or 0),
                    "gold_grams":             float(r.gold_grams or 0),
                    "silver_grams":           float(r.silver_grams or 0),
                    "business_inventory_pkr": float(r.business_inventory_pkr or 0),
                    "receivables_pkr":        float(r.receivables_pkr or 0),
                },
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
    }
