from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
import hashlib
import hmac
import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

app = FastAPI(title="NEXUS LaunchDesk", version="0.4.0")
DB_PATH = Path(os.getenv("NEXUS_DB_PATH", "/data/nexus.db"))
if not DB_PATH.parent.exists():
    DB_PATH = Path("./nexus.db")
ADMIN_TOKEN = os.getenv("NEXUS_ADMIN_TOKEN", "")

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

class OrderUpdate(BaseModel):
    status: str = Field(pattern="^(new|in_progress|completed|cancelled)$")
    payment_status: str = Field(pattern="^(unpaid|pending|paid|refunded)$")


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, status TEXT NOT NULL, payment_status TEXT NOT NULL, offer_id TEXT NOT NULL, offer_name TEXT NOT NULL, price_usd REAL NOT NULL, customer_name TEXT NOT NULL, contact TEXT NOT NULL, notes TEXT NOT NULL)")
    conn.commit()
    return conn


def admin_guard(token: str | None) -> None:
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="Admin token is not configured")
    if not token or not hmac.compare_digest(token, ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Unauthorized")


def trading_mode() -> str:
    return os.getenv("TRADING_MODE", "disabled").strip().lower()


def binance_environment() -> str:
    return os.getenv("BINANCE_ENV", "testnet").strip().lower()


def safety_state() -> dict[str, Any]:
    mode = trading_mode()
    return {"trading_mode": mode, "binance_environment": binance_environment(), "live_orders_enabled": False, "withdrawals_enabled": False, "manual_approval_required": True, "kill_switch": True, "status": "safe" if mode == "disabled" else "restricted"}


def storefront() -> str:
    cards = "".join(f"<article class='card'><h3>{o['name']}</h3><p>{o['description']}</p><strong>${o['price_usd']}</strong><small>{o['delivery']}</small><button onclick=\"choose('{o['id']}')\">اطلب الآن</button></article>" for o in OFFERS)
    options = "".join(f"<option value='{o['id']}'>{o['name']}</option>" for o in OFFERS)
    return f"""<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>NEXUS LaunchDesk</title><style>body{{font-family:system-ui;background:#0b1020;color:#f4f7ff;margin:0}}main{{max-width:1000px;margin:auto;padding:28px}}.hero{{padding:32px 0}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}}.card,form{{background:#151d33;border:1px solid #2d3a5e;border-radius:18px;padding:20px}}.card strong{{display:block;font-size:28px;margin:16px 0}.card small{{display:block;color:#aebbd8;margin-bottom:16px}}button{{background:#6d8cff;color:white;border:0;border-radius:10px;padding:12px 16px;font-weight:700;cursor:pointer}}input,textarea,select{{width:100%;box-sizing:border-box;margin:8px 0 14px;padding:12px;border-radius:10px;border:1px solid #3a486d;background:#0f1629;color:white}}#result{{margin-top:15px;color:#9ef0b5}}</style></head><body><main><section class='hero'><p>خدمات رقمية سريعة للأفراد وأصحاب المشاريع</p><h1>NEXUS LaunchDesk</h1><p>اطلب خدمة واضحة واستلمها عن بُعد.</p></section><section class='grid'>{cards}</section><form id='order' onsubmit='submitOrder(event)'><h2>إرسال طلب</h2><label>الخدمة</label><select id='offer' required>{options}</select><label>الاسم</label><input id='name' required minlength='2'><label>واتساب أو بريد إلكتروني</label><input id='contact' required minlength='4'><label>التفاصيل</label><textarea id='notes' rows='4'></textarea><button type='submit'>إرسال الطلب</button><div id='result'></div></form></main><script>function choose(id){{document.getElementById('offer').value=id;document.getElementById('order').scrollIntoView({{behavior:'smooth'}})}}async function submitOrder(e){{e.preventDefault();const result=document.getElementById('result');result.textContent='جارٍ إرسال الطلب...';const r=await fetch('/api/v1/orders',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{offer_id:document.getElementById('offer').value,customer_name:document.getElementById('name').value,contact:document.getElementById('contact').value,notes:document.getElementById('notes').value}})}});const data=await r.json();result.textContent=r.ok?'تم استلام طلبك رقم '+data.order_id+'. سيتم التواصل معك لتأكيد الدفع.':(data.detail||'تعذر إرسال الطلب');}}</script></body></html>"""


@app.on_event("startup")
def startup() -> None:
    db().close()


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return storefront()

@app.get("/admin", response_class=HTMLResponse)
def admin_page() -> str:
    return """<!doctype html><html lang='ar' dir='rtl'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>NEXUS Admin</title><style>body{font-family:system-ui;background:#0b1020;color:#fff;padding:24px}input,button{padding:10px;margin:5px;border-radius:8px}button{cursor:pointer}pre{white-space:pre-wrap;background:#151d33;padding:16px;border-radius:12px}</style><h1>لوحة تحكم NEXUS</h1><input id='token' type='password' placeholder='Admin token'><button onclick='load()'>عرض الطلبات</button><pre id='out'>أدخل رمز الإدارة ثم اضغط عرض الطلبات.</pre><script>async function load(){const r=await fetch('/api/v1/admin/orders',{headers:{'X-Admin-Token':document.getElementById('token').value}});document.getElementById('out').textContent=JSON.stringify(await r.json(),null,2)}</script></html>"""

@app.get("/api/v1/offers")
def offers() -> list[dict[str, Any]]:
    return OFFERS

@app.post("/api/v1/orders", status_code=201)
def create_order(payload: OrderRequest) -> dict[str, Any]:
    offer = next((o for o in OFFERS if o["id"] == payload.offer_id), None)
    if offer is None:
        raise HTTPException(status_code=404, detail="الخدمة غير موجودة")
    order_id = f"ORD-{uuid4().hex[:10].upper()}"
    with db() as conn:
        conn.execute("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?)", (order_id, datetime.now(timezone.utc).isoformat(), "new", "unpaid", offer["id"], offer["name"], offer["price_usd"], payload.customer_name, payload.contact, payload.notes))
    return {"accepted": True, "order_id": order_id, "status": "new", "next_step": "owner_contact_required"}

@app.get("/api/v1/admin/orders")
def admin_orders(x_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    admin_guard(x_admin_token)
    with db() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()]
    return {"count": len(rows), "orders": rows}

@app.patch("/api/v1/admin/orders/{order_id}")
def update_order(order_id: str, payload: OrderUpdate, x_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    admin_guard(x_admin_token)
    with db() as conn:
        cur = conn.execute("UPDATE orders SET status=?, payment_status=? WHERE id=?", (payload.status, payload.payment_status, order_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="الطلب غير موجود")
    return {"updated": True, "order_id": order_id, **payload.model_dump()}

@app.get("/api/v1/health")
def api_health() -> dict[str, Any]:
    return {"status": "ok", "service": "nexus-launchdesk", "version": app.version, "timestamp": datetime.now(timezone.utc).isoformat()}

@app.get("/health")
def health() -> dict[str, Any]:
    return api_health()

@app.get("/api/v1/status")
def status() -> dict[str, Any]:
    return {"service": "nexus-launchdesk", "version": app.version, "storefront": True, "orders": True, "persistent_storage": True, "admin_dashboard": True, "payment_provider": "not_configured", "settlement": "owner_controlled"}

@app.get("/api/v1/safety")
def safety() -> dict[str, Any]:
    return safety_state()

@app.get("/api/v1/ready")
def readiness() -> dict[str, Any]:
    return {"ready": True, "checks": {"api_process": "ok", "storefront": "ok", "order_intake": "ok", "persistent_storage": "ok", "payment_provider": "not_configured", "admin_token": "configured" if ADMIN_TOKEN else "missing"}}
