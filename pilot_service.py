"""Deployable Oryven Pilot Service.

Purpose: keep Stripe secret/webhook credentials and remote telemetry/feedback
outside the Windows desktop. Deploy behind HTTPS (Railway/Fly/Render/etc.).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

app = FastAPI(title="Oryven Pilot Service", version="0.19.1")
DB = Path(os.environ.get("ORYVEN_PILOT_DB", "/data/oryven-pilot.sqlite3"))
DB.parent.mkdir(parents=True, exist_ok=True)


def db():
    conn = sqlite3.connect(DB, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS subscriptions(user_id TEXT PRIMARY KEY, email TEXT, stripe_customer TEXT, stripe_subscription TEXT, status TEXT, updated_at REAL);
    CREATE TABLE IF NOT EXISTS telemetry(id INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT, properties TEXT, created_at REAL);
    CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, category TEXT, message TEXT, diagnostics TEXT, created_at REAL);
    """)
    return conn


def bearer_guard(authorization: str | None):
    expected = os.environ.get("ORYVEN_PILOT_API_TOKEN", "")
    if not expected:
        raise HTTPException(503, "Pilot API token not configured")
    token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not hmac.compare_digest(token, expected):
        raise HTTPException(401, "Unauthorized")


class CheckoutIn(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    email: EmailStr
    plan: str = "pilot"


class TelemetryIn(BaseModel):
    event: str = Field(min_length=1, max_length=80)
    properties: dict[str, Any] = {}


class FeedbackIn(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    category: str
    message: str = Field(min_length=3, max_length=2000)
    diagnostics: dict[str, Any] = {}


@app.get("/health")
def health():
    return {"status": "ok", "service": "oryven-pilot", "stripe_configured": bool(os.environ.get("STRIPE_SECRET_KEY"))}


@app.post("/v1/billing/checkout")
def create_checkout(body: CheckoutIn, authorization: str | None = Header(default=None)):
    bearer_guard(authorization)
    secret = os.environ.get("STRIPE_SECRET_KEY", "")
    price = os.environ.get("STRIPE_PRICE_PILOT", "")
    success = os.environ.get("STRIPE_SUCCESS_URL", "https://buno.ai/oryven/success")
    cancel = os.environ.get("STRIPE_CANCEL_URL", "https://buno.ai/oryven/cancel")
    if not secret or not price:
        raise HTTPException(503, "Stripe not configured")
    data = {
        "mode": "subscription",
        "success_url": success,
        "cancel_url": cancel,
        "client_reference_id": body.user_id,
        "customer_email": str(body.email),
        "line_items[0][price]": price,
        "line_items[0][quantity]": "1",
        "metadata[user_id]": body.user_id,
        "metadata[plan]": body.plan,
        "subscription_data[metadata][user_id]": body.user_id,
        "subscription_data[metadata][plan]": body.plan,
    }
    try:
        r = httpx.post("https://api.stripe.com/v1/checkout/sessions", headers={"Authorization": f"Bearer {secret}"}, content=urlencode(data), timeout=20)
        if r.status_code >= 400:
            raise HTTPException(502, "Stripe checkout failed")
        obj = r.json()
        return {"checkout_url": obj.get("url"), "session_id": obj.get("id")}
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Stripe unavailable") from exc


def verify_stripe_signature(payload: bytes, header: str, secret: str, tolerance: int = 300) -> None:
    parts = {}
    for item in header.split(","):
        if "=" in item:
            k, v = item.split("=", 1)
            parts.setdefault(k, []).append(v)
    try:
        ts = int(parts["t"][0]); sigs = parts.get("v1", [])
    except Exception as exc:
        raise HTTPException(400, "Invalid Stripe signature") from exc
    if abs(int(time.time()) - ts) > tolerance:
        raise HTTPException(400, "Expired Stripe signature")
    signed = str(ts).encode() + b"." + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, s) for s in sigs):
        raise HTTPException(400, "Invalid Stripe signature")


@app.post("/v1/stripe/webhook")
async def stripe_webhook(request: Request, stripe_signature: str | None = Header(default=None, alias="Stripe-Signature")):
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    if not secret or not stripe_signature:
        raise HTTPException(503, "Stripe webhook not configured")
    payload = await request.body()
    verify_stripe_signature(payload, stripe_signature, secret)
    event = json.loads(payload)
    typ = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}
    if typ in {"checkout.session.completed", "customer.subscription.updated", "customer.subscription.deleted"}:
        user_id = ((obj.get("metadata") or {}).get("user_id") or obj.get("client_reference_id") or "")
        if user_id:
            status = obj.get("status") or ("active" if typ == "checkout.session.completed" else "unknown")
            with db() as c:
                c.execute("INSERT INTO subscriptions(user_id,email,stripe_customer,stripe_subscription,status,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET email=excluded.email,stripe_customer=excluded.stripe_customer,stripe_subscription=excluded.stripe_subscription,status=excluded.status,updated_at=excluded.updated_at",
                          (user_id, obj.get("customer_details",{}).get("email") or obj.get("customer_email"), obj.get("customer"), obj.get("subscription") or obj.get("id"), status, time.time()))
    return {"received": True}


@app.get("/v1/billing/entitlement")
def entitlement(user_id: str, authorization: str | None = Header(default=None)):
    bearer_guard(authorization)
    with db() as c:
        row = c.execute("SELECT * FROM subscriptions WHERE user_id=?", (user_id,)).fetchone()
    if row is None:
        return {"plan":"free","status":"inactive","source":"stripe","expires_at":None}
    status = str(row["status"] or "inactive").lower()
    active = status in {"active","trialing","complete","paid"}
    return {"plan":"pilot" if active else "free", "status":"active" if active else status,
            "source":"stripe", "stripe_subscription":row["stripe_subscription"], "updated_at":row["updated_at"]}


@app.post("/v1/telemetry")
def telemetry(body: TelemetryIn, authorization: str | None = Header(default=None)):
    bearer_guard(authorization)
    allowed = {k: v for k, v in body.properties.items() if k in {"flow","status","duration_bucket","error_class","version","surface"}}
    with db() as c:
        c.execute("INSERT INTO telemetry(event,properties,created_at) VALUES(?,?,?)", (body.event, json.dumps(allowed), time.time()))
    return {"accepted": True}


@app.post("/v1/feedback")
def feedback(body: FeedbackIn, authorization: str | None = Header(default=None)):
    bearer_guard(authorization)
    safe_diag = {k:v for k,v in body.diagnostics.items() if k in {"version","release_channel","voice_provider","buno_reachable","pending_approvals"}}
    with db() as c:
        cur = c.execute("INSERT INTO feedback(user_id,category,message,diagnostics,created_at) VALUES(?,?,?,?,?)", (body.user_id, body.category, body.message, json.dumps(safe_diag), time.time()))
    return {"accepted": True, "feedback_id": cur.lastrowid}
