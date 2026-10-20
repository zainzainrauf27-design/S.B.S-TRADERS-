#!/usr/bin/env python3
"""Dependency-free local-first S.A.B Trader website and API."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import shutil
import sqlite3
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
MIGRATIONS = ROOT / "db" / "migrations"
sys.path.insert(0, str(ROOT / "scripts"))
UTC = timezone.utc
PBKDF2_ROUNDS = 600_000
SESSION_HOURS = 12


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def new_id() -> str:
    return str(uuid.uuid4())


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def password_matches(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_hex, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


@contextmanager
def connect(db_path: Path):
    db = sqlite3.connect(db_path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=15000")
    try:
        with db:
            yield db
    finally:
        db.close()


class App:
    def __init__(self, db_path: Path):
        self.db_path = db_path.resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        from db_migrate import apply_migrations
        apply_migrations(self.db_path)

    def create_admin(self, username: str, display_name: str, password: str) -> None:
        if len(password) < 12:
            raise ValueError("Admin password kam az kam 12 characters ka hona chahiye.")
        with connect(self.db_path) as db:
            if db.execute("SELECT 1 FROM users WHERE role='admin' AND active=1").fetchone():
                raise ValueError("Active Admin pehle se maujood hai.")
            stamp = now()
            user_id=new_id()
            db.execute("INSERT INTO users(id,username,display_name,password_hash,role,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                       (user_id, username, display_name, password_hash(password), "admin", stamp, stamp))
            self.audit(db,user_id,"admin_created","user",user_id,{"username":username})

    def authenticate(self, username: str, password: str) -> tuple[sqlite3.Row | None, str | None]:
        with connect(self.db_path) as db:
            user = db.execute("SELECT * FROM users WHERE username=? COLLATE NOCASE AND active=1", (username,)).fetchone()
            if not user or not password_matches(password, user["password_hash"]):
                time.sleep(0.35)
                return None, None
            token = secrets.token_urlsafe(36)
            expiry = (datetime.now(UTC) + timedelta(hours=SESSION_HOURS)).isoformat(timespec="seconds")
            db.execute("INSERT INTO sessions(id,user_id,token_hash,device_id,created_at,expires_at) VALUES(?,?,?,?,?,?)",
                       (new_id(), user["id"], hashlib.sha256(token.encode()).hexdigest(), "website", now(), expiry))
            db.execute("INSERT INTO audit_events(id,actor_id,action,record_type,record_id,details_json,occurred_at) VALUES(?,?,?,?,?,?,?)",
                       (new_id(), user["id"], "login", "user", user["id"], "{}", now()))
            return user, token

    def user_for_token(self, token: str | None) -> sqlite3.Row | None:
        if not token:
            return None
        token_digest = hashlib.sha256(token.encode()).hexdigest()
        with connect(self.db_path) as db:
            return db.execute("""SELECT u.id,u.username,u.display_name,u.role,s.id AS session_id
                FROM sessions s JOIN users u ON u.id=s.user_id
                WHERE s.token_hash=? AND s.revoked_at IS NULL AND s.expires_at>? AND u.active=1""",
                (token_digest, now())).fetchone()

    def audit(self, db: sqlite3.Connection, actor: str | None, action: str, kind: str, record_id: str | None, details: dict | None = None) -> None:
        db.execute("INSERT INTO audit_events(id,actor_id,action,record_type,record_id,details_json,occurred_at) VALUES(?,?,?,?,?,?,?)",
                   (new_id(), actor, action, kind, record_id, json.dumps(details or {}, separators=(",", ":")), now()))

    def dashboard(self) -> dict:
        with connect(self.db_path) as db:
            today = datetime.now(UTC).date().isoformat()
            products = db.execute("SELECT COUNT(*) n FROM products WHERE active=1").fetchone()["n"]
            customers = db.execute("SELECT COUNT(*) n FROM customers WHERE active=1").fetchone()["n"]
            sales = db.execute("SELECT COUNT(*) n,COALESCE(SUM(total_paisa),0) total FROM sales WHERE status='posted' AND date(sold_at)=?", (today,)).fetchone()
            low = db.execute("SELECT COUNT(*) n FROM products WHERE active=1 AND stock_quantity<=minimum_stock").fetchone()["n"]
            outstanding = db.execute("""SELECT COALESCE(SUM(s.total_paisa-COALESCE(p.paid,0)),0) n FROM sales s
                LEFT JOIN (SELECT sale_id,SUM(CASE WHEN reversal_of IS NULL THEN amount_paisa ELSE -amount_paisa END) paid FROM payments WHERE sale_id IS NOT NULL GROUP BY sale_id) p ON p.sale_id=s.id
                WHERE s.status='posted'""").fetchone()["n"]
            supplier_payables=db.execute("""SELECT COALESCE(SUM(s.opening_balance_paisa+COALESCE(x.purchased,0)-COALESCE(y.paid,0)),0) n FROM suppliers s
                LEFT JOIN (SELECT supplier_id,SUM(total_paisa) purchased FROM purchases WHERE status='posted' GROUP BY supplier_id) x ON x.supplier_id=s.id
                LEFT JOIN (SELECT supplier_id,SUM(CASE WHEN reversal_of IS NULL THEN amount_paisa ELSE -amount_paisa END) paid FROM payments GROUP BY supplier_id) y ON y.supplier_id=s.id""").fetchone()["n"]
            recent = [dict(row) for row in db.execute("SELECT id,invoice_number,customer_name_snapshot,total_paisa,sold_at FROM sales ORDER BY sold_at DESC LIMIT 8")]
            health = db.execute("PRAGMA quick_check").fetchone()[0]
            last_backup = db.execute("SELECT details_json,occurred_at FROM audit_events WHERE action='backup_created' ORDER BY occurred_at DESC LIMIT 1").fetchone()
            return {"products": products, "customers": customers, "today_orders": sales["n"], "today_sales_paisa": sales["total"],
                    "low_stock": low, "outstanding_paisa": outstanding, "supplier_payables_paisa": supplier_payables, "recent": recent, "db_health": health,
                    "last_backup": last_backup["occurred_at"] if last_backup else None}

    def get_products(self, query: str = "") -> list[dict]:
        with connect(self.db_path) as db:
            pattern = f"%{query.strip()}%"
            rows = db.execute("""SELECT p.*,b.name brand,c.name category FROM products p
                LEFT JOIN brands b ON b.id=p.brand_id LEFT JOIN categories c ON c.id=p.category_id
                WHERE (?='' OR p.name LIKE ? OR p.sku LIKE ? OR p.barcode LIKE ? OR b.name LIKE ? OR c.name LIKE ?)
                ORDER BY p.name COLLATE NOCASE LIMIT 500""", (query, pattern, pattern, pattern, pattern, pattern)).fetchall()
            return [dict(r) for r in rows]

    def get_customers(self, query: str = "", admin: bool = True) -> list[dict]:
        with connect(self.db_path) as db:
            pattern = f"%{query.strip()}%"
            rows = db.execute("""SELECT c.*, c.opening_balance_paisa + COALESCE((SELECT SUM(s.total_paisa) FROM sales s WHERE s.customer_id=c.id AND s.status='posted'),0)
                - COALESCE((SELECT SUM(CASE WHEN p.reversal_of IS NULL THEN p.amount_paisa ELSE -p.amount_paisa END) FROM payments p WHERE p.customer_id=c.id),0) balance_paisa
                FROM customers c WHERE (?='' OR c.name LIKE ? OR c.phone LIKE ? OR c.area LIKE ?) ORDER BY c.name COLLATE NOCASE LIMIT 500""",
                (query, pattern, pattern, pattern)).fetchall()
            result = [dict(r) for r in rows]
            if not admin:
                for row in result:
                    row.pop("balance_paisa", None)
            return result

    def create_sale(self, actor: sqlite3.Row, payload: dict) -> dict:
        sale_id = str(payload.get("id") or new_id())
        items = payload.get("items")
        if not isinstance(items, list) or not items or len(items) > 100:
            raise ValueError("Order mein 1 se 100 products zaroori hain.")
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT id,invoice_number,total_paisa FROM sales WHERE id=?", (sale_id,)).fetchone()
            if previous:
                return {"id": previous["id"], "invoice_number": previous["invoice_number"], "total_paisa": previous["total_paisa"], "duplicate": True}
            customer_id = payload.get("customer_id") or None
            customer = db.execute("SELECT * FROM customers WHERE id=? AND active=1", (customer_id,)).fetchone() if customer_id else None
            if customer_id and not customer:
                raise ValueError("Customer mojood ya active nahin.")
            subtotal = 0
            computed = []
            for item in items:
                product = db.execute("SELECT * FROM products WHERE id=? AND active=1", (item.get("product_id"),)).fetchone()
                quantity = int(item.get("quantity", 0))
                if not product or quantity <= 0:
                    raise ValueError("Product ya quantity durust nahin.")
                if product["stock_quantity"] < quantity:
                    raise ValueError(f"'{product['name']}' ka stock kafi nahin.")
                if actor["role"] == "staff" and int(item.get("unit_price_paisa", -1)) != product["wholesale_price_paisa"]:
                    raise ValueError("Staff sirf muqarrar wholesale price par order kar sakta hai.")
                unit = int(item.get("unit_price_paisa", product["wholesale_price_paisa"]))
                discount = int(item.get("discount_paisa", 0)) if actor["role"] == "admin" else 0
                if unit < 0 or discount < 0 or discount > quantity * unit:
                    raise ValueError("Price ya discount durust nahin.")
                line = quantity * unit - discount
                subtotal += line
                computed.append((product, quantity, unit, discount, line))
            invoice_discount = int(payload.get("discount_paisa", 0)) if actor["role"] == "admin" else 0
            if invoice_discount < 0 or invoice_discount > subtotal:
                raise ValueError("Invoice discount durust nahin.")
            total = subtotal - invoice_discount
            invoice_prefix = db.execute("SELECT setting_value FROM business_settings WHERE setting_key='invoice_prefix'").fetchone()[0]
            sequence = db.execute("SELECT COUNT(*) n FROM sales").fetchone()["n"] + 1
            invoice = f"{invoice_prefix}-{sequence:06d}"
            stamp = now()
            db.execute("INSERT INTO sales(id,invoice_number,customer_id,customer_name_snapshot,customer_phone_snapshot,sold_at,subtotal_paisa,discount_paisa,total_paisa,status,staff_id,notes,created_at) VALUES(?,?,?,?,?,?,?,?,?,'posted',?,?,?)",
                       (sale_id, invoice, customer_id, customer["name"] if customer else str(payload.get("customer_name") or "Walk-in"), customer["phone"] if customer else None,
                        stamp, subtotal, invoice_discount, total, actor["id"], str(payload.get("notes") or "")[:1000], stamp))
            for product, quantity, unit, discount, line in computed:
                db.execute("INSERT INTO sale_items(id,sale_id,product_id,product_name_snapshot,quantity,unit_price_paisa,unit_cost_paisa,discount_paisa,line_total_paisa) VALUES(?,?,?,?,?,?,?,?,?)",
                           (new_id(), sale_id, product["id"], product["name"], quantity, unit, product["purchase_cost_paisa"], discount, line))
                db.execute("UPDATE products SET stock_quantity=stock_quantity-?,updated_at=? WHERE id=?", (quantity, stamp, product["id"]))
                db.execute("INSERT INTO stock_movements(id,product_id,quantity_delta,unit_cost_paisa,reason,source_type,source_id,actor_id,occurred_at) VALUES(?,?,?,?,?,?,?,?,?)",
                           (new_id(), product["id"], -quantity, product["purchase_cost_paisa"], "sale", "sale", sale_id, actor["id"], stamp))
            paid = int(payload.get("paid_paisa", 0))
            if paid < 0 or paid > total:
                raise ValueError("Paid amount total se zyada ya manfi nahin ho sakta.")
            if paid:
                db.execute("INSERT INTO payments(id,payment_number,customer_id,sale_id,amount_paisa,method,paid_at,recorded_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                           (new_id(), f"PAY-{uuid.uuid4().hex[:12].upper()}", customer_id, sale_id, paid, str(payload.get("payment_method") or "Cash")[:40], stamp, actor["id"], stamp))
            self.audit(db, actor["id"], "sale_created", "sale", sale_id, {"invoice": invoice, "total_paisa": total})
            return {"id": sale_id, "invoice_number": invoice, "total_paisa": total, "duplicate": False}

    def receipt(self, sale_id: str) -> dict | None:
        with connect(self.db_path) as db:
            sale = db.execute("SELECT s.*,u.display_name staff_name FROM sales s JOIN users u ON u.id=s.staff_id WHERE s.id=?", (sale_id,)).fetchone()
            if not sale:
                return None
            items = [dict(r) for r in db.execute("SELECT * FROM sale_items WHERE sale_id=?", (sale_id,))]
            paid = db.execute("SELECT COALESCE(SUM(CASE WHEN reversal_of IS NULL THEN amount_paisa ELSE -amount_paisa END),0) n FROM payments WHERE sale_id=?", (sale_id,)).fetchone()["n"]
            settings = {r["setting_key"]: r["setting_value"] for r in db.execute("SELECT * FROM business_settings")}
            method = db.execute("SELECT method FROM payments WHERE sale_id=? AND reversal_of IS NULL ORDER BY paid_at LIMIT 1", (sale_id,)).fetchone()
            return {**dict(sale), "items": items, "paid_paisa": paid, "balance_paisa": sale["total_paisa"] - paid, "payment_method": method["method"] if method else "Credit", "settings": settings}

    def save_customer(self, actor: sqlite3.Row, payload: dict) -> dict:
        name = str(payload.get("name") or "").strip()
        if not name or len(name) > 160:
            raise ValueError("Customer ka naam zaroori hai (max 160 characters).")
        customer_id = str(payload.get("id") or new_id())
        stamp = now()
        opening = int(payload.get("opening_balance_paisa", 0)) if actor["role"] == "admin" else 0
        credit_limit = payload.get("credit_limit_paisa") if actor["role"] == "admin" else None
        with connect(self.db_path) as db:
            db.execute("INSERT INTO customers(id,name,phone,address,area,opening_balance_paisa,credit_limit_paisa,notes,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                       (customer_id, name, str(payload.get("phone") or "")[:40], str(payload.get("address") or "")[:300], str(payload.get("area") or "")[:120], opening, credit_limit, str(payload.get("notes") or "")[:1000], actor["id"], stamp, stamp))
            self.audit(db, actor["id"], "customer_created", "customer", customer_id)
        return {"id": customer_id, "name": name}

    def save_payment(self, actor: sqlite3.Row, payload: dict) -> dict:
        payment_id = str(payload.get("id") or new_id())
        amount = int(payload.get("amount_paisa", 0))
        if amount <= 0:
            raise ValueError("Payment amount zero se zyada hona chahiye.")
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT id,payment_number FROM payments WHERE id=?", (payment_id,)).fetchone()
            if old: return {"id": old["id"], "payment_number": old["payment_number"], "duplicate": True}
            customer_id = payload.get("customer_id")
            sale_id = payload.get("sale_id")
            customer = db.execute("SELECT id FROM customers WHERE id=? AND active=1", (customer_id,)).fetchone()
            if not customer: raise ValueError("Active customer select karein.")
            if sale_id:
                sale = db.execute("SELECT id,customer_id,total_paisa,status FROM sales WHERE id=?", (sale_id,)).fetchone()
                if not sale or sale["customer_id"] != customer_id or sale["status"] != "posted": raise ValueError("Sale customer se match nahin karti.")
                received = db.execute("SELECT COALESCE(SUM(CASE WHEN reversal_of IS NULL THEN amount_paisa ELSE -amount_paisa END),0) n FROM payments WHERE sale_id=?", (sale_id,)).fetchone()["n"]
                if amount + received > sale["total_paisa"]: raise ValueError("Payment invoice ke baqi balance se zyada hai.")
            stamp=now(); number=f"PAY-{uuid.uuid4().hex[:12].upper()}"
            db.execute("INSERT INTO payments(id,payment_number,customer_id,sale_id,amount_paisa,method,paid_at,note,recorded_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (payment_id,number,customer_id,sale_id,amount,str(payload.get("method") or "Cash")[:40],stamp,str(payload.get("note") or "")[:500],actor["id"],stamp))
            self.audit(db,actor["id"],"payment_recorded","payment",payment_id,{"amount_paisa":amount,"customer_id":customer_id})
            return {"id":payment_id,"payment_number":number,"duplicate":False}

    def customer_ledger(self, customer_id: str) -> dict | None:
        with connect(self.db_path) as db:
            customer=db.execute("SELECT * FROM customers WHERE id=?",(customer_id,)).fetchone()
            if not customer:return None
            sales=[dict(r) for r in db.execute("SELECT id,invoice_number,sold_at,total_paisa,status FROM sales WHERE customer_id=? ORDER BY sold_at DESC",(customer_id,))]
            payments=[dict(r) for r in db.execute("SELECT id,payment_number,sale_id,amount_paisa,method,paid_at,note,reversal_of FROM payments WHERE customer_id=? ORDER BY paid_at DESC",(customer_id,))]
            balance=customer["opening_balance_paisa"]+sum(s["total_paisa"] for s in sales if s["status"]=="posted")-sum((-p["amount_paisa"] if p["reversal_of"] else p["amount_paisa"]) for p in payments)
            return {"customer":dict(customer),"sales":sales,"payments":payments,"balance_paisa":balance}

    def get_suppliers(self, query: str = "") -> list[dict]:
        with connect(self.db_path) as db:
            pattern=f"%{query.strip()}%"
            rows=db.execute("""SELECT s.*,s.opening_balance_paisa+COALESCE((SELECT SUM(p.total_paisa) FROM purchases p WHERE p.supplier_id=s.id AND p.status='posted'),0)
                -COALESCE((SELECT SUM(CASE WHEN py.reversal_of IS NULL THEN py.amount_paisa ELSE -py.amount_paisa END) FROM payments py WHERE py.supplier_id=s.id),0) balance_paisa
                FROM suppliers s WHERE (?='' OR s.name LIKE ? OR s.phone LIKE ?) ORDER BY s.name COLLATE NOCASE""",(query,pattern,pattern)).fetchall()
            return [dict(r) for r in rows]

    def create_purchase(self, actor: sqlite3.Row, payload: dict) -> dict:
        purchase_id=str(payload.get("id") or new_id());items=payload.get("items")
        if not isinstance(items,list) or not items or len(items)>100:raise ValueError("Purchase mein products add karein.")
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            prev=db.execute("SELECT purchase_number,total_paisa FROM purchases WHERE id=?",(purchase_id,)).fetchone()
            if prev:return {"id":purchase_id,"purchase_number":prev["purchase_number"],"total_paisa":prev["total_paisa"],"duplicate":True}
            supplier=db.execute("SELECT id FROM suppliers WHERE id=? AND active=1",(payload.get("supplier_id"),)).fetchone()
            if not supplier:raise ValueError("Active supplier select karein.")
            calculated=[];subtotal=0
            for item in items:
                product=db.execute("SELECT * FROM products WHERE id=? AND active=1",(item.get("product_id"),)).fetchone();qty=int(item.get("quantity",0));cost=int(item.get("unit_cost_paisa",0))
                if not product or qty<=0 or cost<0:raise ValueError("Product, quantity ya unit cost durust nahin.")
                line=qty*cost;subtotal+=line;calculated.append((product,qty,cost,line))
            discount=int(payload.get("discount_paisa",0))
            if discount<0 or discount>subtotal:raise ValueError("Purchase discount durust nahin.")
            total=subtotal-discount;paid=int(payload.get("paid_paisa",0))
            if paid<0 or paid>total:raise ValueError("Paid amount purchase total se zyada nahin ho sakta.")
            stamp=now();seq=db.execute("SELECT COUNT(*) n FROM purchases").fetchone()["n"]+1;number=f"PUR-{seq:06d}"
            db.execute("INSERT INTO purchases(id,purchase_number,supplier_id,purchased_at,subtotal_paisa,discount_paisa,total_paisa,amount_paid_paisa,status,notes,created_by,created_at) VALUES(?,?,?,?,?,?,?,?, 'posted',?,?,?)",(purchase_id,number,payload["supplier_id"],stamp,subtotal,discount,total,paid,str(payload.get("notes") or "")[:1000],actor["id"],stamp))
            for product,qty,cost,line in calculated:
                db.execute("INSERT INTO purchase_items(id,purchase_id,product_id,product_name,quantity,unit_cost_paisa,line_total_paisa) VALUES(?,?,?,?,?,?,?)",(new_id(),purchase_id,product["id"],product["name"],qty,cost,line))
                db.execute("UPDATE products SET stock_quantity=stock_quantity+?,purchase_cost_paisa=?,updated_at=? WHERE id=?",(qty,cost,stamp,product["id"]))
                db.execute("INSERT INTO stock_movements(id,product_id,quantity_delta,unit_cost_paisa,reason,source_type,source_id,actor_id,occurred_at) VALUES(?,?,?,?,?,?,?,?,?)",(new_id(),product["id"],qty,cost,"purchase","purchase",purchase_id,actor["id"],stamp))
            if paid:
                db.execute("INSERT INTO payments(id,payment_number,supplier_id,purchase_id,amount_paisa,method,paid_at,recorded_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)",(new_id(),f"PAY-{uuid.uuid4().hex[:12].upper()}",payload["supplier_id"],purchase_id,paid,str(payload.get("payment_method") or "Cash")[:40],stamp,actor["id"],stamp))
            self.audit(db,actor["id"],"purchase_created","purchase",purchase_id,{"purchase_number":number,"total_paisa":total})
            return {"id":purchase_id,"purchase_number":number,"total_paisa":total,"duplicate":False}

    def reverse_payment(self,actor:sqlite3.Row,payment_id:str)->dict:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE");payment=db.execute("SELECT * FROM payments WHERE id=? AND reversal_of IS NULL",(payment_id,)).fetchone()
            if not payment:raise ValueError("Original payment nahin mila.")
            if db.execute("SELECT 1 FROM payments WHERE reversal_of=?",(payment_id,)).fetchone():raise ValueError("Payment pehle reverse ho chuki hai.")
            reversal_id=new_id();stamp=now();number=f"REV-{uuid.uuid4().hex[:12].upper()}"
            db.execute("INSERT INTO payments(id,payment_number,customer_id,supplier_id,sale_id,purchase_id,amount_paisa,method,paid_at,reversal_of,note,recorded_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (reversal_id,number,payment["customer_id"],payment["supplier_id"],payment["sale_id"],payment["purchase_id"],payment["amount_paisa"],payment["method"],stamp,payment_id,"Authorized reversal",actor["id"],stamp))
            self.audit(db,actor["id"],"payment_reversed","payment",payment_id,{"reversal_id":reversal_id})
            return {"id":reversal_id,"payment_number":number}

    def reverse_sale(self,actor:sqlite3.Row,sale_id:str,final_status:str="cancelled")->dict:
        if final_status not in {"cancelled","returned"}:raise ValueError("Sale reversal type durust nahin.")
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE");sale=db.execute("SELECT * FROM sales WHERE id=? AND status='posted'",(sale_id,)).fetchone()
            if not sale:raise ValueError("Posted sale nahin mili ya pehle reverse ho chuki hai.")
            paid=db.execute("SELECT COALESCE(SUM(CASE WHEN reversal_of IS NULL THEN amount_paisa ELSE -amount_paisa END),0) n FROM payments WHERE sale_id=?",(sale_id,)).fetchone()["n"]
            if paid:raise ValueError("Sale cancel karne se pehle related payments reverse karein.")
            stamp=now()
            for item in db.execute("SELECT * FROM sale_items WHERE sale_id=?",(sale_id,)).fetchall():
                db.execute("UPDATE products SET stock_quantity=stock_quantity+?,updated_at=? WHERE id=?",(item["quantity"],stamp,item["product_id"]))
                db.execute("INSERT INTO stock_movements(id,product_id,quantity_delta,unit_cost_paisa,reason,source_type,source_id,actor_id,occurred_at) VALUES(?,?,?,?,?,?,?,?,?)",(new_id(),item["product_id"],item["quantity"],item["unit_cost_paisa"],"sale_cancelled","sale",sale_id,actor["id"],stamp))
            db.execute("UPDATE sales SET status=? WHERE id=?",(final_status,sale_id));self.audit(db,actor["id"],"sale_"+final_status,"sale",sale_id)
            return {"ok":True,"status":final_status}

    def reverse_purchase(self,actor:sqlite3.Row,purchase_id:str)->dict:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE");purchase=db.execute("SELECT * FROM purchases WHERE id=? AND status='posted'",(purchase_id,)).fetchone()
            if not purchase:raise ValueError("Posted purchase nahin mili ya pehle reverse ho chuki hai.")
            paid=db.execute("SELECT COALESCE(SUM(CASE WHEN reversal_of IS NULL THEN amount_paisa ELSE -amount_paisa END),0) n FROM payments WHERE purchase_id=?",(purchase_id,)).fetchone()["n"]
            if paid:raise ValueError("Purchase reverse karne se pehle related supplier payments reverse karein.")
            items=db.execute("SELECT * FROM purchase_items WHERE purchase_id=?",(purchase_id,)).fetchall()
            for item in items:
                stock=db.execute("SELECT stock_quantity FROM products WHERE id=?",(item["product_id"],)).fetchone()["stock_quantity"]
                if stock<item["quantity"]:raise ValueError("Maujooda stock purchase reverse karne ke liye kafi nahin.")
            stamp=now()
            for item in items:
                db.execute("UPDATE products SET stock_quantity=stock_quantity-?,updated_at=? WHERE id=?",(item["quantity"],stamp,item["product_id"]))
                db.execute("INSERT INTO stock_movements(id,product_id,quantity_delta,unit_cost_paisa,reason,source_type,source_id,actor_id,occurred_at) VALUES(?,?,?,?,?,?,?,?,?)",(new_id(),item["product_id"],-item["quantity"],item["unit_cost_paisa"],"purchase_reversed","purchase",purchase_id,actor["id"],stamp))
            db.execute("UPDATE purchases SET status='reversed' WHERE id=?",(purchase_id,));self.audit(db,actor["id"],"purchase_reversed","purchase",purchase_id)
            return {"ok":True}


class Handler(BaseHTTPRequestHandler):
    server_version = "SABTrader/1.0"
    app: App
    request_lock = threading.RLock()
    login_attempts: dict[str, tuple[int, float]] = {}

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"{self.log_date_time_string()} {self.address_string()} {fmt % args}\n")

    def handle_one_request(self) -> None:
        with self.request_lock:
            super().handle_one_request()

    def send_json(self, status: int, data: dict | list) -> None:
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 1_000_000:
            raise ValueError("Request bohat bara hai.")
        if not length:
            return {}
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise ValueError("Request format durust nahin.")
        return value

    def token(self) -> str | None:
        value = self.headers.get("Authorization", "")
        return value[7:] if value.lower().startswith("bearer ") else None

    def require_user(self, admin: bool = False) -> sqlite3.Row | None:
        user = self.app.user_for_token(self.token())
        if not user:
            self.send_json(401, {"error": "Login dobara karein."})
            return None
        if admin and user["role"] != "admin":
            self.send_json(403, {"error": "Is feature ke liye Admin access chahiye."})
            return None
        return user

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self.send_json(200, {"status": "ok"}); return
        if parsed.path.startswith("/api/"):
            user = self.require_user()
            if not user: return
            query = parse_qs(parsed.query)
            if parsed.path == "/api/me": self.send_json(200, dict(user)); return
            if parsed.path == "/api/dashboard":
                self.send_json(200, self.app.dashboard() if user["role"] == "admin" else {"my_orders": self._my_orders(user["id"]), "role": "staff"}); return
            if parsed.path == "/api/products":
                rows = self.app.get_products(query.get("q", [""])[0])
                if user["role"] == "staff":
                    for row in rows: row.pop("purchase_cost_paisa", None)
                self.send_json(200, rows); return
            if parsed.path == "/api/customers": self.send_json(200, self.app.get_customers(query.get("q", [""])[0], user["role"] == "admin")); return
            if parsed.path == "/api/sales":
                with connect(self.app.db_path) as db:
                    where = "" if user["role"] == "admin" else "WHERE s.staff_id=?"
                    params = () if user["role"] == "admin" else (user["id"],)
                    rows = db.execute(f"SELECT s.id,s.invoice_number,s.customer_name_snapshot,s.sold_at,s.total_paisa,s.status,u.display_name staff_name FROM sales s JOIN users u ON u.id=s.staff_id {where} ORDER BY s.sold_at DESC LIMIT 300", params).fetchall()
                    self.send_json(200, [dict(r) for r in rows]); return
            if parsed.path.startswith("/api/receipt/"):
                data = self.app.receipt(parsed.path.rsplit("/", 1)[-1])
                if data and user["role"] == "staff":
                    with connect(self.app.db_path) as db:
                        owner = db.execute("SELECT staff_id FROM sales WHERE id=?", (data["id"],)).fetchone()
                    if not owner or owner["staff_id"] != user["id"]: data = None
                    else:
                        for item in data["items"]: item.pop("unit_cost_paisa", None)
                self.send_json(200 if data else 404, data or {"error": "Invoice nahin mili."}); return
            if parsed.path == "/api/attendance":
                with connect(self.app.db_path) as db:
                    if user["role"] == "admin": rows = db.execute("SELECT a.*,u.display_name FROM attendance a JOIN users u ON u.id=a.user_id ORDER BY checked_in_at DESC LIMIT 500").fetchall()
                    else: rows = db.execute("SELECT * FROM attendance WHERE user_id=? ORDER BY checked_in_at DESC LIMIT 100", (user["id"],)).fetchall()
                    self.send_json(200, [dict(r) for r in rows]); return
            if parsed.path == "/api/settings":
                if user["role"] != "admin": self.send_json(403, {"error": "Admin access chahiye."}); return
                with connect(self.app.db_path) as db:
                    settings={r["setting_key"]: r["setting_value"] for r in db.execute("SELECT * FROM business_settings")}
                    settings["database_path"]=str(self.app.db_path);settings["backup_path"]=str(self.app.db_path.parent)
                    self.send_json(200,settings); return
            if parsed.path == "/api/staff":
                if user["role"] != "admin": self.send_json(403, {"error": "Admin access chahiye."}); return
                with connect(self.app.db_path) as db:
                    self.send_json(200, [dict(r) for r in db.execute("SELECT id,username,display_name,role,active,created_at FROM users ORDER BY display_name")]); return
            if parsed.path == "/api/suppliers":
                if user["role"]!="admin": self.send_json(403,{"error":"Sirf Admin supplier records dekh sakta hai."});return
                self.send_json(200,self.app.get_suppliers(query.get("q",[""])[0]));return
            if parsed.path == "/api/purchases":
                if user["role"]!="admin": self.send_json(403,{"error":"Sirf Admin purchases dekh sakta hai."});return
                with connect(self.app.db_path) as db:self.send_json(200,[dict(r) for r in db.execute("SELECT p.id,p.purchase_number,p.purchased_at,p.total_paisa,p.status,s.name supplier_name FROM purchases p JOIN suppliers s ON s.id=p.supplier_id ORDER BY p.purchased_at DESC LIMIT 300")]);return
            if parsed.path.startswith("/api/customer/") and parsed.path.endswith("/ledger"):
                if user["role"] != "admin": self.send_json(403, {"error": "Customer ledger sirf Admin dekh sakta hai."}); return
                customer_id=parsed.path.split("/")[3]; data=self.app.customer_ledger(customer_id)
                self.send_json(200 if data else 404,data or {"error":"Customer nahin mila."});return
            self.send_json(404, {"error": "Endpoint nahin mila."}); return
        self.serve_static(parsed.path)

    def _my_orders(self, user_id: str) -> list[dict]:
        with connect(self.app.db_path) as db:
            return [dict(r) for r in db.execute("SELECT invoice_number,customer_name_snapshot,total_paisa,sold_at FROM sales WHERE staff_id=? ORDER BY sold_at DESC LIMIT 8", (user_id,))]

    def do_POST(self) -> None:
        try:
            payload = self.body()
            path = urlparse(self.path).path
            if path == "/api/login":
                key=f"{self.client_address[0]}:{str(payload.get('username','')).casefold()}";count,locked=self.login_attempts.get(key,(0,0.0))
                if time.monotonic()<locked: self.send_json(429,{"error":"Bohat zyada login koshishain. Kuch dair baad dobara koshish karein."});return
                user, token = self.app.authenticate(str(payload.get("username", "")), str(payload.get("password", "")))
                if not user:
                    count+=1;self.login_attempts[key]=(0,time.monotonic()+300) if count>=5 else (count,0.0)
                    self.send_json(401, {"error": "Username ya password durust nahin."}); return
                self.login_attempts.pop(key,None)
                self.send_json(200, {"token": token, "user": {"id": user["id"], "display_name": user["display_name"], "role": user["role"]}}); return
            user = self.require_user()
            if not user: return
            if path == "/api/logout":
                token = self.token()
                if token:
                    with connect(self.app.db_path) as db:
                        db.execute("UPDATE sessions SET revoked_at=? WHERE token_hash=?", (now(), hashlib.sha256(token.encode()).hexdigest()))
                        self.app.audit(db, user["id"], "logout", "user", user["id"])
                self.send_json(200, {"ok": True}); return
            if path == "/api/customers": self.send_json(201, self.app.save_customer(user, payload)); return
            if path == "/api/sales": self.send_json(201, self.app.create_sale(user, payload)); return
            if path == "/api/payments":
                if user["role"]!="admin": self.send_json(403,{"error":"Sirf Admin alag customer payments record kar sakta hai."});return
                self.send_json(201, self.app.save_payment(user, payload)); return
            if path == "/api/suppliers":
                if user["role"]!="admin":self.send_json(403,{"error":"Sirf Admin supplier add kar sakta hai."});return
                name=str(payload.get("name") or "").strip()
                if not name:raise ValueError("Supplier ka naam zaroori hai.")
                supplier_id=new_id();stamp=now()
                with connect(self.app.db_path) as db:
                    db.execute("INSERT INTO suppliers(id,name,phone,address,opening_balance_paisa,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",(supplier_id,name,str(payload.get("phone") or "")[:40],str(payload.get("address") or "")[:300],int(payload.get("opening_balance_paisa",0)),str(payload.get("notes") or "")[:1000],stamp,stamp))
                    self.app.audit(db,user["id"],"supplier_created","supplier",supplier_id)
                self.send_json(201,{"id":supplier_id,"name":name});return
            if path == "/api/purchases":
                if user["role"]!="admin":self.send_json(403,{"error":"Sirf Admin purchase post kar sakta hai."});return
                self.send_json(201,self.app.create_purchase(user,payload));return
            if path == "/api/staff":
                if user["role"] != "admin": self.send_json(403, {"error":"Admin access chahiye."}); return
                username=str(payload.get("username") or "").strip(); name=str(payload.get("display_name") or "").strip(); password=str(payload.get("password") or "")
                if not username or not name or len(password)<12: raise ValueError("Username, naam aur kam az kam 12 character password dein.")
                stamp=now(); staff_id=new_id()
                with connect(self.app.db_path) as db:
                    db.execute("INSERT INTO users(id,username,display_name,password_hash,role,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",(staff_id,username,name,password_hash(password),"staff",stamp,stamp))
                    self.app.audit(db,user["id"],"staff_created","user",staff_id,{"username":username})
                self.send_json(201,{"id":staff_id,"username":username});return
            if path.startswith("/api/products/") and path.endswith("/adjust"):
                if user["role"]!="admin": self.send_json(403,{"error":"Sirf Admin stock adjust kar sakta hai."});return
                product_id=path.split("/")[3];delta=int(payload.get("quantity_delta",0));reason=str(payload.get("reason") or "").strip()
                if delta==0 or not reason: raise ValueError("Stock change aur wajah zaroori hai.")
                stamp=now()
                with connect(self.app.db_path) as db:
                    db.execute("BEGIN IMMEDIATE");row=db.execute("SELECT stock_quantity FROM products WHERE id=?",(product_id,)).fetchone()
                    if not row: raise ValueError("Product nahin mila.")
                    if row["stock_quantity"]+delta<0: raise ValueError("Stock zero se neeche nahin ja sakta.")
                    db.execute("UPDATE products SET stock_quantity=stock_quantity+?,updated_at=? WHERE id=?",(delta,stamp,product_id))
                    db.execute("INSERT INTO stock_movements(id,product_id,quantity_delta,reason,actor_id,occurred_at,note) VALUES(?,?,?,?,?,?,?)",(new_id(),product_id,delta,reason,user["id"],stamp,str(payload.get("note") or "")[:500]))
                    self.app.audit(db,user["id"],"stock_adjusted","product",product_id,{"delta":delta,"reason":reason})
                self.send_json(200,{"ok":True});return
            if path == "/api/attendance/check-in":
                stamp = now()
                with connect(self.app.db_path) as db:
                    db.execute("INSERT INTO attendance(id,user_id,checked_in_at,created_at) VALUES(?,?,?,?)", (new_id(), user["id"], stamp, stamp))
                    self.app.audit(db, user["id"], "attendance_check_in", "attendance", None)
                self.send_json(201, {"ok": True}); return
            if path == "/api/attendance/check-out":
                with connect(self.app.db_path) as db:
                    row = db.execute("SELECT id FROM attendance WHERE user_id=? AND checked_out_at IS NULL", (user["id"],)).fetchone()
                    if not row: self.send_json(409, {"error": "Open check-in nahin mila."}); return
                    db.execute("UPDATE attendance SET checked_out_at=? WHERE id=?", (now(), row["id"]))
                    self.app.audit(db, user["id"], "attendance_check_out", "attendance", row["id"])
                self.send_json(200, {"ok": True}); return
            if path == "/api/products":
                if user["role"] != "admin": self.send_json(403, {"error": "Sirf Admin product add kar sakta hai."}); return
                self._create_product(user, payload); return
            if path == "/api/settings":
                if user["role"] != "admin": self.send_json(403, {"error": "Admin access chahiye."}); return
                self._save_settings(user, payload); return
            if path == "/api/backup":
                if user["role"] != "admin": self.send_json(403, {"error": "Admin access chahiye."}); return
                self._backup(user, payload); return
            if path == "/api/restore":
                if user["role"] != "admin": self.send_json(403,{"error":"Admin access chahiye."});return
                self._restore(user,payload);return
            if path.startswith("/api/sales/") and path.endswith("/reverse"):
                if user["role"]!="admin":self.send_json(403,{"error":"Sirf Admin sale reverse kar sakta hai."});return
                self.send_json(200,self.app.reverse_sale(user,path.split("/")[3],str(payload.get("status","cancelled"))));return
            if path.startswith("/api/purchases/") and path.endswith("/reverse"):
                if user["role"]!="admin":self.send_json(403,{"error":"Sirf Admin purchase reverse kar sakta hai."});return
                self.send_json(200,self.app.reverse_purchase(user,path.split("/")[3]));return
            if path.startswith("/api/payments/") and path.endswith("/reverse"):
                if user["role"]!="admin":self.send_json(403,{"error":"Sirf Admin payment reverse kar sakta hai."});return
                self.send_json(201,self.app.reverse_payment(user,path.split("/")[3]));return
            self.send_json(404, {"error": "Endpoint nahin mila."})
        except sqlite3.IntegrityError as exc:
            message = "Record duplicate hai ya related data mojood nahin."
            if "attendance_one_open_shift" in str(exc): message = "Aaj ka check-in pehle se open hai."
            self.send_json(409, {"error": message})
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            self.send_json(400, {"error": str(exc) or "Request durust nahin."})
        except Exception as exc:
            sys.stderr.write(f"request error: {type(exc).__name__}: {exc}\n")
            self.send_json(500, {"error": "Server mein masla aaya. Logs check karein."})

    def _create_product(self, user: sqlite3.Row, p: dict) -> None:
        name = str(p.get("name") or "").strip()
        price = int(p.get("wholesale_price_paisa", -1))
        if not name or len(name) > 200 or price < 0: raise ValueError("Product name aur wholesale price durust dein.")
        product_id, stamp = str(p.get("id") or new_id()), now()
        opening = int(p.get("stock_quantity", 0))
        if opening < 0: raise ValueError("Opening stock manfi nahin ho sakta.")
        with connect(self.app.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO products(id,sku,barcode,name,unit,purchase_cost_paisa,wholesale_price_paisa,retail_price_paisa,stock_quantity,minimum_stock,active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,1,?,?)",
                       (product_id, p.get("sku") or None, p.get("barcode") or None, name, str(p.get("unit") or "piece"), int(p.get("purchase_cost_paisa", 0)), price, p.get("retail_price_paisa"), opening, int(p.get("minimum_stock", 0)), stamp, stamp))
            if opening:
                db.execute("INSERT INTO stock_movements(id,product_id,quantity_delta,unit_cost_paisa,reason,actor_id,occurred_at) VALUES(?,?,?,?,?,?,?)",
                           (new_id(), product_id, opening, int(p.get("purchase_cost_paisa", 0)), "opening_stock", user["id"], stamp))
            self.app.audit(db, user["id"], "product_created", "product", product_id)
        self.send_json(201, {"id": product_id, "name": name})

    def _save_settings(self, user: sqlite3.Row, payload: dict) -> None:
        allowed = {"business_name", "business_type", "company_phone", "business_address", "business_email", "timezone", "currency", "invoice_prefix", "receipt_width_mm", "developer_footer_enabled", "receipt_footer"}
        stamp = now()
        with connect(self.app.db_path) as db:
            for key, value in payload.items():
                if key in allowed:
                    db.execute("INSERT INTO business_settings(setting_key,setting_value,updated_at) VALUES(?,?,?) ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value,updated_at=excluded.updated_at", (key, str(value)[:500], stamp))
            self.app.audit(db, user["id"], "settings_updated", "business_settings", None, {"keys": sorted(set(payload) & allowed)})
        self.send_json(200, {"ok": True})

    def _backup(self, user: sqlite3.Row, payload: dict) -> None:
        destination = Path(str(payload.get("path") or "")).expanduser().resolve()
        if destination == self.app.db_path or destination.suffix.lower() not in {".sqlite", ".db"}:
            raise ValueError("Backup ke liye alag .sqlite ya .db file select karein.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = sqlite3.connect(self.app.db_path, timeout=15)
        target = sqlite3.connect(destination)
        try:
            source.backup(target)
            check = target.execute("PRAGMA integrity_check").fetchone()[0]
            if check != "ok": raise ValueError("Backup integrity check fail hua.")
        finally:
            target.close(); source.close()
        with connect(self.app.db_path) as db: self.app.audit(db, user["id"], "backup_created", "backup", None, {"filename": destination.name})
        self.send_json(201, {"ok": True, "filename": destination.name})

    def _restore(self,user:sqlite3.Row,payload:dict)->None:
        selected=Path(str(payload.get("path") or "")).expanduser().resolve()
        if not selected.is_file() or selected==self.app.db_path:raise ValueError("Mojood, alag backup database file select karein.")
        current_ids={p.stem for p in MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql")}
        candidate=sqlite3.connect(selected.as_uri()+"?mode=ro",uri=True)
        try:
            integrity=candidate.execute("PRAGMA integrity_check").fetchone()[0]
            fk=candidate.execute("PRAGMA foreign_key_check").fetchall()
            applied={r[0] for r in candidate.execute("SELECT migration_id FROM schema_migrations")}
            if integrity!="ok" or fk or "001_initial" not in applied or not applied.issubset(current_ids):
                raise ValueError("Backup ki integrity ya schema compatibility verify nahin hui.")
            stamp=datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            safety=self.app.db_path.with_name(f"{self.app.db_path.stem}.pre-restore-{stamp}.sqlite")
            temp=self.app.db_path.with_name(f"{self.app.db_path.stem}.restore-tmp.sqlite")
            with connect(self.app.db_path) as source:
                safe=sqlite3.connect(safety)
                try:source.backup(safe)
                finally:safe.close()
            restored=sqlite3.connect(temp)
            try:candidate.backup(restored)
            finally:restored.close()
        finally:candidate.close()
        check=sqlite3.connect(temp)
        try:
            if check.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("Restore temporary copy integrity check fail hua.")
        finally:check.close()
        with connect(self.app.db_path) as db:db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        for suffix in ("-wal","-shm"):
            side=Path(str(self.app.db_path)+suffix)
            if side.exists():side.unlink()
        try:
            os.replace(temp,self.app.db_path)
            from db_migrate import apply_migrations
            apply_migrations(self.app.db_path)
            with connect(self.app.db_path) as db:
                actor_id=user["id"] if db.execute("SELECT 1 FROM users WHERE id=?",(user["id"],)).fetchone() else None
                self.app.audit(db,actor_id,"restore_completed","backup",None,{"source":selected.name,"safety_backup":safety.name,"restored_by":user["username"]})
        except Exception:
            if safety.exists():shutil.copy2(safety,self.app.db_path)
            raise
        self.send_json(200,{"ok":True,"safety_backup":safety.name})

    def do_PUT(self) -> None:
        try:
            payload = self.body()
            if urlparse(self.path).path.startswith("/api/products/"):
                user = self.require_user(admin=True)
                if not user: return
                product_id = urlparse(self.path).path.rsplit("/", 1)[-1]
                allowed = {"name", "sku", "barcode", "unit", "purchase_cost_paisa", "wholesale_price_paisa", "retail_price_paisa", "minimum_stock", "active"}
                fields = {k: payload[k] for k in allowed if k in payload}
                if not fields: raise ValueError("Update karne ke liye fields nahin mile.")
                with connect(self.app.db_path) as db:
                    assignments = ",".join(f"{k}=?" for k in fields)
                    db.execute(f"UPDATE products SET {assignments},updated_at=? WHERE id=?", (*fields.values(), now(), product_id))
                    self.app.audit(db, user["id"], "product_updated", "product", product_id, {"fields": sorted(fields)})
                self.send_json(200, {"ok": True}); return
            self.send_json(404, {"error": "Endpoint nahin mila."})
        except Exception as exc:
            self.send_json(400, {"error": str(exc)})

    def serve_static(self, path: str) -> None:
        route = "/index.html" if path in ("/", "") else path
        target = (WEB / route.lstrip("/")).resolve()
        if not target.is_relative_to(WEB.resolve()) or not target.is_file():
            self.send_error(404); return
        mime = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml"}.get(target.suffix, "application/octet-stream")
        content = target.read_bytes()
        self.send_response(200); self.send_header("Content-Type", mime); self.send_header("Content-Length", str(len(content))); self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        self.end_headers(); self.wfile.write(content)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    server = sub.add_parser("serve", help="Run the local website")
    server.add_argument("--db", type=Path)
    server.add_argument("--host", default="127.0.0.1", help="Default is local-only; LAN requires explicit host")
    server.add_argument("--port", type=int, default=8765)
    admin = sub.add_parser("create-admin", help="Create the first Admin account")
    admin.add_argument("--db", type=Path)
    admin.add_argument("--username", required=True)
    admin.add_argument("--name", required=True)
    args = parser.parse_args()
    if args.db:
        database = args.db.resolve()
    else:
        database = Path(os.environ.get("LOCALAPPDATA", str(ROOT / "work"))) / "SABTrader" / "data" / "sabtrader.sqlite"
    app = App(database)
    if args.command == "create-admin":
        import getpass
        pw = getpass.getpass("Naya Admin password (minimum 12 characters): ")
        confirm = getpass.getpass("Password dobara likhein: ")
        if pw != confirm: raise SystemExit("Passwords match nahin karte.")
        app.create_admin(args.username, args.name, pw)
        print(f"Admin '{args.username}' create ho gaya. Password sirf aap ke paas rahega.")
        return 0
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        print("Warning: LAN access selected. Sirf trusted network par chalayein; public internet par port forward na karein.", file=sys.stderr)
    Handler.app = app
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"S.A.B Trader website: http://127.0.0.1:{args.port}")
    print(f"SQLite database: {database}")
    try: httpd.serve_forever()
    except KeyboardInterrupt: print("\nWebsite band ho rahi hai...")
    finally: httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
