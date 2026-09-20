from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

app = FastAPI(title="NEXUS LaunchDesk", version="0.3.1")
ORDERS: list[dict[str, Any]] = []
OFFERS = [
    {"id": "cv-ar", "name": "سيرة ذاتية احترافية", "description": "سيرة عربية أو إنجليزية متوافقة مع ATS.", "price_usd": 12, "delivery": "24-48 ساعة"},
    {"id": "business-kit", "name": "حزمة إطلاق مشروع صغير", "description": "اسم تجاري ووصف خدمات وعرض أسعار ونصوص تسويقية.", "price_usd": 25, "delivery": "48-72 ساعة"},
    {"id": "automation-audit", "name": "مراجعة أتمتة الأعمال", "description": "تحديد 5 مهام قابلة للأتمتة مع خطة تنفيذ.", "price_usd": 35, "delivery": "48-72 ساعة"},
]

class OrderRequest(BaseModel):
    offer_id: str = Field(min_length=2, max_length=64)
    customer_name: str = Field(min_length=2, max_length=120)
    contact: str = Field(min_length=4, max_length=180)
    notes: str = Field(default="", max_length=2000)


def trading_mode() -> str:
    return os.getenv("TRADING_MODE", "disabled").strip().lower()


def binance_environment() -> str:
    return os.getenv("BINANCE_ENV", "testnet").strip().lower()


def safety_state() -> dict[str, Any]:
    mode = trading_mode()
    return {"trading_mode": mode, "binance_environment": binance_environment(), "live_orders_enabled": False, "withdrawals_enabled": False, "manual_approval_required": True, "kill_switch": True, "status": "safe" if mode == "disabled" else "restricted"}


@app.get("/", response_class=HTMLResponse)
def storefront() -> str:
    cards = "".join(f"<article class='card'><h3>{o['name']}</h3><p>{o['description']}</p><strong>${o['price_usd']}</strong><small>{o['delivery']}</small><button onclick=\"choose('{o['id']}')\">اطلب الآن</button></article>" for o in OFFERS)
    options = "".join(f"<option value='{o['id']}'>{o['name']}</option>" for o in OFFERS)
    return f"""<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>NEXUS LaunchDesk</title><style>body{{font-family:system-ui;background:#0b1020;color:#f4f7ff;margin:0}}main{{max-width:1000px;margin:auto;padding:28px}}.hero{{padding:32px 0}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}}.card,form{{background:#151d33;border:1px solid #2d3a5e;border-radius:18px;padding:20px}}.card strong{{display:block;font-size:28px;margin:16px 0}.card small{{display:block;color:#aebbd8;margin-bottom:16px}}button{{background:#6d8cff;color:white;border:0;border-radius:10px;padding:12px 16px;font-weight:700;cursor:pointer}}input,textarea,select{{width:100%;box-sizing:border-box;margin:8px 0 14px;padding:12px;border-radius:10px;border:1px solid #3a486d;background:#0f1629;color:white}}#result{{margin-top:15px;color:#9ef0b5}}</style></head><body><main><section class='hero'><p>خدمات رقمية سريعة للأفراد وأصحاب المشاريع</p><h1>NEXUS LaunchDesk</h1><p>اطلب خدمة واضحة واستلمها عن بُعد.</p></section><section class='grid'>{cards}</section><form id='order' onsubmit='submitOrder(event)'><h2>إرسال طلب</h2><label>الخدمة</label><select id='offer' required>{options}</select><label>الاسم</label><input id='name' required minlength='2'><label>واتساب أو بريد إلكتروني</label><input id='contact' required minlength='4'><label>التفاصيل</label><textarea id='notes' rows='4'></textarea><button type='submit'>إرسال الطلب</button><div id='result'></div></form></main><script>function choose(id){{document.getElementById('offer').value=id;document.getElementById('order').scrollIntoView({{behavior:'smooth'}})}}async function submitOrder(e){{e.preventDefault();const result=document.getElementById('result');result.textContent='جارٍ إرسال الطلب...';const r=await fetch('/api/v1/orders',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{offer_id:document.getElementById('offer').value,customer_name:document.getElementById('name').value,contact:document.getElementById('contact').value,notes:document.getElementById('notes').value}})}});const data=await r.json();result.textContent=r.ok?'تم استلام طلبك. سيتم التواصل معك لتأكيد السعر وطريقة الدفع.':(data.detail||'تعذر إرسال الطلب');}}</script></body></html>"""


@app.get("/api/v1/offers")
def offers() -> list[dict[str, Any]]:
    return OFFERS


@app.post("/api/v1/orders", status_code=201)
def create_order(payload: OrderRequest) -> dict[str, Any]:
    offer = next((o for o in OFFERS if o["id"] == payload.offer_id), None)
    if offer is None:
        raise HTTPException(status_code=404, detail="الخدمة غير موجودة")
    order = {"id": f"ORD-{uuid4().hex[:10].upper()}", "created_at": datetime.now(timezone.utc).isoformat(), "status": "new", "payment_status": "unpaid", "offer": offer, **payload.model_dump()}
    ORDERS.append(order)
    return {"accepted": True, "order_id": order["id"], "status": "new", "next_step": "owner_contact_required"}


@app.get("/api/v1/orders")
def list_orders() -> dict[str, Any]:
    return {"count": len(ORDERS), "orders": ORDERS}


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "nexus-launchdesk", "version": app.version, "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/v1/status")
def status() -> dict[str, Any]:
    return {"service": "nexus-launchdesk", "version": app.version, "storefront": True, "orders": True, "payment_provider": "not_configured", "settlement": "owner_controlled"}


@app.get("/api/v1/safety")
def safety() -> dict[str, Any]:
    return safety_state()


@app.get("/api/v1/ready")
def readiness() -> dict[str, Any]:
    return {"ready": True, "checks": {"api_process": "ok", "storefront": "ok", "order_intake": "ok", "payment_provider": "not_configured"}}
