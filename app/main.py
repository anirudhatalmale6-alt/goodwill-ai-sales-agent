import os
import json
from datetime import datetime
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .database import get_db, init_db, seed_database

app = FastAPI(title="Goodwill AI Sales Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.on_event("startup")
def startup():
    init_db()


# ─── Dashboard Routes ───

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/products", response_class=HTMLResponse)
async def products_page(request: Request):
    return templates.TemplateResponse("products.html", {"request": request})


@app.get("/customers", response_class=HTMLResponse)
async def customers_page(request: Request):
    return templates.TemplateResponse("customers.html", {"request": request})


@app.get("/orders-page", response_class=HTMLResponse)
async def orders_page(request: Request):
    return templates.TemplateResponse("orders.html", {"request": request})


@app.get("/calls", response_class=HTMLResponse)
async def calls_page(request: Request):
    return templates.TemplateResponse("calls.html", {"request": request})


# ─── Product API (used by ElevenLabs agent tools + dashboard) ───

@app.get("/api/products")
async def list_products(department: str = None, category: str = None, search: str = None,
                        own_brand: bool = None, limit: int = 50, offset: int = 0):
    conn = get_db()
    query = "SELECT * FROM products WHERE 1=1"
    params = []

    if department:
        query += " AND department = ?"
        params.append(department.lower().strip())
    if category:
        query += " AND category LIKE ?"
        params.append(f"%{category.lower().strip()}%")
    if search:
        s = f"%{search.lower().strip()}%"
        query += " AND (LOWER(description) LIKE ? OR LOWER(name_alternative) LIKE ? OR LOWER(category) LIKE ?)"
        params.extend([s, s, s])
    if own_brand is not None:
        query += " AND own_brand = ?"
        params.append(1 if own_brand else 0)

    query += " ORDER BY own_brand DESC, priority_pricing DESC, price ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(query, params).fetchall()
    total = conn.execute(
        "SELECT COUNT(*) FROM products WHERE 1=1" + query.split("WHERE 1=1")[1].rsplit("LIMIT", 1)[0],
        params[:-2]
    ).fetchone()[0]
    conn.close()

    return {
        "products": [dict(r) for r in rows],
        "total": total
    }


@app.get("/api/products/{product_id}")
async def get_product(product_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Product not found")
    return dict(row)


@app.post("/api/products/{product_id}")
async def update_product(product_id: int, request: Request):
    data = await request.json()
    conn = get_db()
    fields = []
    values = []
    for key in ["description", "price", "packing", "uom", "name_alternative",
                "specification", "stock_available", "own_brand", "priority_pricing"]:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        raise HTTPException(400, "No fields to update")
    fields.append("updated_at = ?")
    values.append(datetime.now().isoformat())
    values.append(product_id)
    conn.execute(f"UPDATE products SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return {"status": "updated"}


@app.get("/api/products/search/voice")
async def voice_product_search(query: str):
    """Search products by name, alternative name, or category - optimized for voice agent."""
    conn = get_db()
    q = query.lower().strip()

    results = conn.execute("""
        SELECT id, code, department, category, name_alternative, description,
               packing, uom, price, own_brand, priority_pricing, specification
        FROM products
        WHERE (LOWER(description) LIKE ? OR LOWER(name_alternative) LIKE ?
               OR LOWER(category) LIKE ? OR LOWER(department) LIKE ?)
          AND priority_pricing = 1
        ORDER BY own_brand DESC, price ASC
    """, (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()

    if not results:
        results = conn.execute("""
            SELECT id, code, department, category, name_alternative, description,
                   packing, uom, price, own_brand, priority_pricing, specification
            FROM products
            WHERE LOWER(description) LIKE ? OR LOWER(name_alternative) LIKE ?
                  OR LOWER(category) LIKE ? OR LOWER(department) LIKE ?
            ORDER BY priority_pricing DESC, own_brand DESC, price ASC
        """, (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()

    conn.close()

    products = []
    for r in results:
        p = dict(r)
        label = p["description"]
        if p["own_brand"]:
            label += " [OWN BRAND]"
        if p["priority_pricing"]:
            label += " [PRIORITY]"
        p["display_label"] = label
        products.append(p)

    return {"products": products, "count": len(products)}


@app.get("/api/departments")
async def list_departments():
    conn = get_db()
    rows = conn.execute("""
        SELECT department, COUNT(*) as product_count
        FROM products GROUP BY department ORDER BY department
    """).fetchall()
    conn.close()
    return {"departments": [dict(r) for r in rows]}


# ─── Customer API ───

@app.get("/api/customers")
async def list_customers(search: str = None):
    conn = get_db()
    if search:
        s = f"%{search.lower()}%"
        rows = conn.execute("""
            SELECT c.*, GROUP_CONCAT(cc.phone_number || ':' || cc.contact_person, '|') as contacts
            FROM customers c
            LEFT JOIN customer_contacts cc ON cc.customer_id = c.id AND cc.is_active = 1
            WHERE LOWER(c.customer_name) LIKE ? OR c.customer_code LIKE ?
            GROUP BY c.id
        """, (s, s)).fetchall()
    else:
        rows = conn.execute("""
            SELECT c.*, GROUP_CONCAT(cc.phone_number || ':' || cc.contact_person, '|') as contacts
            FROM customers c
            LEFT JOIN customer_contacts cc ON cc.customer_id = c.id AND cc.is_active = 1
            GROUP BY c.id
        """).fetchall()
    conn.close()

    customers = []
    for r in rows:
        d = dict(r)
        contacts = []
        if d.get("contacts"):
            for pair in d["contacts"].split("|"):
                parts = pair.split(":", 1)
                if len(parts) == 2:
                    contacts.append({"phone": parts[0], "person": parts[1]})
        d["contact_list"] = contacts
        customers.append(d)

    return {"customers": customers}


@app.get("/api/customers/by-phone/{phone}")
async def get_customer_by_phone(phone: str):
    """Identify customer by phone number - used by voice agent."""
    conn = get_db()
    phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
    if phone_clean.startswith("974"):
        phone_clean = phone_clean[3:]

    row = conn.execute("""
        SELECT c.*, cc.contact_person as caller_name,
               cs.calling_time, cs.rescheduled_time
        FROM customer_contacts cc
        JOIN customers c ON c.id = cc.customer_id
        LEFT JOIN customer_call_schedule cs ON cs.customer_id = c.id
        WHERE cc.phone_number = ? AND cc.is_active = 1
    """, (phone_clean,)).fetchone()

    if not row:
        row = conn.execute("""
            SELECT c.*, cc.contact_person as caller_name,
                   cs.calling_time, cs.rescheduled_time
            FROM customer_contacts cc
            JOIN customers c ON c.id = cc.customer_id
            LEFT JOIN customer_call_schedule cs ON cs.customer_id = c.id
            WHERE cc.phone_number LIKE ? AND cc.is_active = 1
        """, (f"%{phone_clean[-8:]}",)).fetchone()

    if not row:
        conn.close()
        return {"found": False, "message": "Customer not found for this phone number"}

    all_contacts = conn.execute("""
        SELECT contact_person, phone_number FROM customer_contacts
        WHERE customer_id = ? AND is_active = 1
    """, (row["id"],)).fetchall()

    recent_orders = conn.execute("""
        SELECT order_number, total_amount, status, created_at
        FROM orders WHERE customer_id = ?
        ORDER BY created_at DESC LIMIT 5
    """, (row["id"],)).fetchall()

    conn.close()

    return {
        "found": True,
        "customer": {
            "id": row["id"],
            "code": row["customer_code"],
            "name": row["customer_name"],
            "location": row["location"],
            "payment_terms": row["payment_terms"],
            "caller_name": row["caller_name"],
            "calling_time": row["calling_time"],
            "rescheduled_time": row["rescheduled_time"],
            "contacts": [dict(c) for c in all_contacts],
            "recent_orders": [dict(o) for o in recent_orders]
        }
    }


@app.post("/api/customers/{customer_id}/add-phone")
async def add_customer_phone(customer_id: int, request: Request):
    """Add a new phone number to a customer - used by voice agent on the fly."""
    data = await request.json()
    phone = data.get("phone_number", "").replace("+", "").replace(" ", "")
    person = data.get("contact_person", "unknown")
    added_by = data.get("added_by", "ai_agent")

    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM customer_contacts WHERE customer_id = ? AND phone_number = ?",
        (customer_id, phone)
    ).fetchone()

    if existing:
        conn.close()
        return {"status": "already_exists"}

    conn.execute("""
        INSERT INTO customer_contacts (customer_id, contact_person, phone_number, added_by)
        VALUES (?, ?, ?, ?)
    """, (customer_id, person.lower(), phone, added_by))
    conn.commit()
    conn.close()
    return {"status": "added"}


@app.post("/api/customers")
async def create_customer(request: Request):
    data = await request.json()
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO customers (customer_code, customer_name, location, payment_terms)
        VALUES (?, ?, ?, ?)
    """, (data.get("customer_code"), data.get("customer_name", "").lower(),
          data.get("location", "").lower(), data.get("payment_terms", "cash")))
    customer_id = c.lastrowid

    if data.get("phone_number"):
        c.execute("""
            INSERT INTO customer_contacts (customer_id, contact_person, phone_number, added_by)
            VALUES (?, ?, ?, ?)
        """, (customer_id, data.get("contact_person", ""), data["phone_number"], "dashboard"))

    if data.get("calling_time"):
        c.execute("""
            INSERT INTO customer_call_schedule (customer_id, calling_time)
            VALUES (?, ?)
        """, (customer_id, data["calling_time"]))

    conn.commit()
    conn.close()
    return {"status": "created", "customer_id": customer_id}


@app.put("/api/customers/{customer_id}")
async def update_customer(customer_id: int, request: Request):
    data = await request.json()
    conn = get_db()
    fields = []
    values = []
    for key in ["customer_name", "location", "payment_terms", "order_status"]:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if fields:
        fields.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(customer_id)
        conn.execute(f"UPDATE customers SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    conn.close()
    return {"status": "updated"}


# ─── Order API ───

@app.get("/api/orders")
async def list_orders(status: str = None, customer_id: int = None, limit: int = 50):
    conn = get_db()
    query = """
        SELECT o.*, c.customer_name, c.customer_code
        FROM orders o
        LEFT JOIN customers c ON c.id = o.customer_id
        WHERE 1=1
    """
    params = []
    if status:
        query += " AND o.status = ?"
        params.append(status)
    if customer_id:
        query += " AND o.customer_id = ?"
        params.append(customer_id)
    query += " ORDER BY o.created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return {"orders": [dict(r) for r in rows]}


@app.get("/api/orders/{order_id}")
async def get_order(order_id: int):
    conn = get_db()
    order = conn.execute("""
        SELECT o.*, c.customer_name, c.customer_code
        FROM orders o LEFT JOIN customers c ON c.id = o.customer_id
        WHERE o.id = ?
    """, (order_id,)).fetchone()
    if not order:
        conn.close()
        raise HTTPException(404, "Order not found")

    items = conn.execute("""
        SELECT oi.*, p.department, p.category
        FROM order_items oi
        LEFT JOIN products p ON p.id = oi.product_id
        WHERE oi.order_id = ?
    """, (order_id,)).fetchall()
    conn.close()

    return {"order": dict(order), "items": [dict(i) for i in items]}


@app.post("/api/orders")
async def create_order(request: Request):
    """Create a new order - used by voice agent after taking order."""
    data = await request.json()
    conn = get_db()
    c = conn.cursor()

    order_num = f"GW-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    customer_id = data.get("customer_id")
    items = data.get("items", [])

    total = sum(item.get("total_price", 0) for item in items)
    wallet_discount = data.get("wallet_discount", 0)
    wallet_upsell = data.get("wallet_upsell", 0)

    delivery = data.get("delivery_schedule", "")
    if not delivery:
        from datetime import datetime as dt
        hour = dt.now().hour
        if hour >= 14 or hour < 6:
            delivery = "morning (5 AM dispatch)"
        else:
            delivery = "afternoon (2:30 PM dispatch)"

    c.execute("""
        INSERT INTO orders (order_number, customer_id, caller_phone, caller_name,
            total_amount, payment_terms, delivery_schedule, status, notes,
            wallet_discount, wallet_upsell, wallet_balance, conversation_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'confirmed', ?, ?, ?, ?, ?)
    """, (order_num, customer_id, data.get("caller_phone"), data.get("caller_name"),
          total, data.get("payment_terms", "cash"), delivery, data.get("notes"),
          wallet_discount, wallet_upsell, wallet_upsell - wallet_discount,
          data.get("conversation_id")))
    order_id = c.lastrowid

    for item in items:
        c.execute("""
            INSERT INTO order_items (order_id, product_id, product_description,
                packing, uom, quantity, unit_price, total_price, discount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (order_id, item.get("product_id"), item.get("product_description"),
              item.get("packing"), item.get("uom"), item.get("quantity", 1),
              item.get("unit_price"), item.get("total_price"), item.get("discount", 0)))

    conn.commit()
    conn.close()

    return {
        "status": "created",
        "order_id": order_id,
        "order_number": order_num,
        "total_amount": total,
        "delivery_schedule": delivery
    }


@app.put("/api/orders/{order_id}/status")
async def update_order_status(order_id: int, request: Request):
    data = await request.json()
    conn = get_db()
    conn.execute("UPDATE orders SET status = ?, updated_at = ? WHERE id = ?",
                 (data["status"], datetime.now().isoformat(), order_id))
    conn.commit()
    conn.close()
    return {"status": "updated"}


# ─── Call Log API ───

@app.get("/api/call-logs")
async def list_call_logs(limit: int = 50, has_complaint: bool = None,
                         callback_required: bool = None):
    conn = get_db()
    query = """
        SELECT cl.*, c.customer_name
        FROM call_logs cl
        LEFT JOIN customers c ON c.id = cl.customer_id
        WHERE 1=1
    """
    params = []
    if has_complaint is not None:
        query += " AND cl.has_complaint = ?"
        params.append(1 if has_complaint else 0)
    if callback_required is not None:
        query += " AND cl.callback_required = ?"
        params.append(1 if callback_required else 0)
    query += " ORDER BY cl.created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return {"call_logs": [dict(r) for r in rows]}


@app.post("/api/call-logs")
async def create_call_log(request: Request):
    """Log a call - used by voice agent after conversation ends."""
    data = await request.json()
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO call_logs (conversation_id, caller_phone, customer_id, customer_name,
            direction, language, duration_seconds, status, summary, transcript,
            order_id, has_complaint, complaint_details, callback_required, callback_reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (data.get("conversation_id"), data.get("caller_phone"),
          data.get("customer_id"), data.get("customer_name"),
          data.get("direction", "inbound"), data.get("language"),
          data.get("duration_seconds"), data.get("status", "completed"),
          data.get("summary"), data.get("transcript"),
          data.get("order_id"), data.get("has_complaint", 0),
          data.get("complaint_details"), data.get("callback_required", 0),
          data.get("callback_reason")))

    if data.get("has_complaint") and data.get("complaint_details"):
        c.execute("""
            INSERT INTO complaints (customer_id, call_log_id, category, description)
            VALUES (?, ?, ?, ?)
        """, (data.get("customer_id"), c.lastrowid,
              data.get("complaint_category", "general"),
              data["complaint_details"]))

    conn.commit()
    conn.close()
    return {"status": "logged"}


# ─── Complaints API ───

@app.get("/api/complaints")
async def list_complaints(status: str = None):
    conn = get_db()
    query = """
        SELECT comp.*, c.customer_name, cl.caller_phone
        FROM complaints comp
        LEFT JOIN customers c ON c.id = comp.customer_id
        LEFT JOIN call_logs cl ON cl.id = comp.call_log_id
        WHERE 1=1
    """
    params = []
    if status:
        query += " AND comp.status = ?"
        params.append(status)
    query += " ORDER BY comp.created_at DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return {"complaints": [dict(r) for r in rows]}


# ─── Dashboard Stats API ───

@app.get("/api/stats")
async def get_stats():
    conn = get_db()

    total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    today_orders = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE DATE(created_at) = DATE('now')"
    ).fetchone()[0]
    total_revenue = conn.execute(
        "SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE status != 'cancelled'"
    ).fetchone()[0]
    total_calls = conn.execute("SELECT COUNT(*) FROM call_logs").fetchone()[0]
    today_calls = conn.execute(
        "SELECT COUNT(*) FROM call_logs WHERE DATE(created_at) = DATE('now')"
    ).fetchone()[0]
    open_complaints = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE status = 'open'"
    ).fetchone()[0]
    pending_callbacks = conn.execute(
        "SELECT COUNT(*) FROM call_logs WHERE callback_required = 1"
    ).fetchone()[0]
    total_products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    total_customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]

    conn.close()

    return {
        "total_orders": total_orders,
        "today_orders": today_orders,
        "total_revenue": round(total_revenue, 2),
        "total_calls": total_calls,
        "today_calls": today_calls,
        "open_complaints": open_complaints,
        "pending_callbacks": pending_callbacks,
        "total_products": total_products,
        "total_customers": total_customers,
    }


# ─── ElevenLabs Webhook Endpoint ───

@app.post("/api/webhook/elevenlabs")
async def elevenlabs_webhook(request: Request):
    """Receives post-conversation data from ElevenLabs agent."""
    data = await request.json()
    return {"status": "received"}


# ─── Data Reload ───

@app.post("/api/reload-data")
async def reload_data():
    """Reload products and customers from Excel files."""
    seed_database()
    return {"status": "reloaded"}


# ─── Agent Tool Endpoints (called by ElevenLabs webhooks) ───

@app.post("/api/agent/search_products")
async def agent_search_products(request: Request):
    """Webhook tool: search products for voice agent."""
    data = await request.json()
    query = data.get("query", "")
    if not query:
        return {"message": "Please specify a product name or category"}

    conn = get_db()
    q = query.lower().strip()

    results = conn.execute("""
        SELECT id, code, department, category, name_alternative, description,
               packing, uom, price, own_brand, priority_pricing, specification
        FROM products
        WHERE (LOWER(description) LIKE ? OR LOWER(name_alternative) LIKE ?
               OR LOWER(category) LIKE ? OR LOWER(department) LIKE ?)
        ORDER BY priority_pricing DESC, own_brand DESC, price ASC
    """, (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
    conn.close()

    if not results:
        return {"message": f"Sorry, we don't have {query} in our inventory. Would you like something else?"}

    lines = []
    for r in results:
        r = dict(r)
        line = f"{r['description']} - {r['price']} riyal per {r['uom']}"
        if r["own_brand"]:
            line += " (OWN BRAND - recommended)"
        if r["specification"]:
            line += f" ({r['specification']})"
        lines.append(line)

    return {
        "products_found": len(results),
        "product_list": "\n".join(lines),
        "products": [dict(r) for r in results],
    }


@app.post("/api/agent/identify_customer")
async def agent_identify_customer(request: Request):
    """Webhook tool: identify customer by phone or name."""
    data = await request.json()
    phone = data.get("phone_number", "")
    name = data.get("customer_name", "")

    conn = get_db()

    if phone:
        phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
        if phone_clean.startswith("974"):
            phone_clean = phone_clean[3:]

        row = conn.execute("""
            SELECT c.id, c.customer_code, c.customer_name, c.location,
                   c.payment_terms, cc.contact_person,
                   cs.calling_time, cs.rescheduled_time
            FROM customer_contacts cc
            JOIN customers c ON c.id = cc.customer_id
            LEFT JOIN customer_call_schedule cs ON cs.customer_id = c.id
            WHERE cc.phone_number LIKE ? AND cc.is_active = 1
        """, (f"%{phone_clean[-8:]}",)).fetchone()

        if row:
            conn.close()
            return {
                "found": True,
                "customer_id": row["id"],
                "customer_code": row["customer_code"],
                "customer_name": row["customer_name"],
                "location": row["location"],
                "payment_terms": row["payment_terms"],
                "contact_person": row["contact_person"],
                "calling_time": row["calling_time"],
                "rescheduled_time": row["rescheduled_time"],
                "greeting": "Hello sir, welcome back to Goodwill!"
            }

    if name:
        row = conn.execute("""
            SELECT id, customer_code, customer_name, location, payment_terms
            FROM customers WHERE LOWER(customer_name) LIKE ?
        """, (f"%{name.lower()}%",)).fetchone()

        if row:
            conn.close()
            return {
                "found": True,
                "customer_id": row["id"],
                "customer_code": row["customer_code"],
                "customer_name": row["customer_name"],
                "location": row["location"],
                "payment_terms": row["payment_terms"],
                "greeting": "Hello sir, welcome back to Goodwill!"
            }

    # Trial phase: default to beach restaurant (customer_code 2004) when no match found
    row = conn.execute("""
        SELECT c.id, c.customer_code, c.customer_name, c.location,
               c.payment_terms, cs.calling_time, cs.rescheduled_time
        FROM customers c
        LEFT JOIN customer_call_schedule cs ON cs.customer_id = c.id
        WHERE c.customer_code = 2004
    """).fetchone()
    conn.close()

    if row:
        return {
            "found": True,
            "customer_id": row["id"],
            "customer_code": row["customer_code"],
            "customer_name": row["customer_name"],
            "location": row["location"],
            "payment_terms": row["payment_terms"],
            "calling_time": row["calling_time"],
            "rescheduled_time": row["rescheduled_time"],
            "greeting": "Hello sir, welcome back to Goodwill!",
            "note": "Trial mode: defaulted to beach restaurant"
        }

    return {
        "found": False,
        "message": "I couldn't find this customer in our system. Let me note your details - what is your shop name and location?"
    }


@app.post("/api/agent/create_order")
async def agent_create_order(request: Request):
    """Webhook tool: create order from voice agent."""
    data = await request.json()
    conn = get_db()
    c = conn.cursor()

    order_num = f"GW-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    customer_id = data.get("customer_id")
    items = data.get("items", [])

    for item in items:
        if not item.get("total_price") and item.get("unit_price") and item.get("quantity"):
            item["total_price"] = round(item["unit_price"] * item["quantity"], 2)
        if not item.get("unit_price") and item.get("product_id"):
            prod = conn.execute("SELECT price FROM products WHERE id = ?",
                                (item["product_id"],)).fetchone()
            if prod:
                item["unit_price"] = prod["price"]
                item["total_price"] = round(prod["price"] * item.get("quantity", 1), 2)

    gross_total = round(sum(item.get("total_price", 0) for item in items), 2)
    total_discount = round(sum(
        item.get("discount", 0) * item.get("quantity", 1) for item in items
    ), 2)
    net_total = round(gross_total - total_discount, 2)

    wallet_upsell = data.get("wallet_upsell", 0)
    wallet_discount = data.get("wallet_discount", total_discount)

    delivery = data.get("delivery_schedule", "")
    if not delivery:
        hour = datetime.now().hour
        if hour >= 14 or hour < 6:
            delivery = "morning (5 AM dispatch)"
        else:
            delivery = "afternoon (2:30 PM dispatch)"

    c.execute("""
        INSERT INTO orders (order_number, customer_id, caller_phone, caller_name,
            total_amount, payment_terms, delivery_schedule, status, notes,
            wallet_discount, wallet_upsell, wallet_balance, conversation_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'confirmed', ?, ?, ?, ?, ?)
    """, (order_num, customer_id, data.get("caller_phone"), data.get("caller_name"),
          net_total, data.get("payment_terms", "cash"), delivery, data.get("notes"),
          wallet_discount, wallet_upsell, wallet_upsell - wallet_discount,
          data.get("conversation_id")))
    order_id = c.lastrowid

    for idx, item in enumerate(items, 1):
        c.execute("""
            INSERT INTO order_items (order_id, product_id, product_description,
                packing, uom, quantity, unit_price, total_price, discount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (order_id, item.get("product_id"), item.get("product_description"),
              item.get("packing"), item.get("uom"), item.get("quantity", 1),
              item.get("unit_price"), item.get("total_price"), item.get("discount", 0)))

    if wallet_upsell > 0:
        c.execute("""
            INSERT INTO wallet_transactions (customer_id, order_id, transaction_type, amount, description)
            VALUES (?, ?, 'upsell_credit', ?, ?)
        """, (customer_id, order_id, wallet_upsell, f"Upsell credit from order {order_num}"))

    if total_discount > 0:
        c.execute("""
            INSERT INTO wallet_transactions (customer_id, order_id, transaction_type, amount, description)
            VALUES (?, ?, 'discount_debit', ?, ?)
        """, (customer_id, order_id, -total_discount, f"Discount applied on order {order_num}"))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "order_id": order_id,
        "order_number": order_num,
        "gross_total": gross_total,
        "discount": total_discount,
        "net_total": net_total,
        "total_amount": net_total,
        "delivery_schedule": delivery,
        "confirmation_message": f"Your order {order_num} has been confirmed. Gross total is {gross_total} riyals, discount {total_discount} riyals, net total {net_total} riyals. Delivery will be {delivery}. Please hand over the amount to the delivery person."
    }


@app.post("/api/agent/log_call")
async def agent_log_call(request: Request):
    """Webhook tool: log call from voice agent."""
    data = await request.json()
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO call_logs (conversation_id, caller_phone, customer_id, customer_name,
            direction, language, status, summary,
            has_complaint, complaint_details, callback_required, callback_reason, order_id)
        VALUES (?, ?, ?, ?, 'inbound', ?, 'completed', ?, ?, ?, ?, ?, ?)
    """, (data.get("conversation_id"), data.get("caller_phone"),
          data.get("customer_id"), data.get("customer_name"),
          data.get("language", "english"), data.get("summary"),
          1 if data.get("has_complaint") else 0,
          data.get("complaint_details"),
          1 if data.get("callback_required") else 0,
          data.get("callback_reason"),
          data.get("order_id")))

    if data.get("has_complaint") and data.get("complaint_details"):
        c.execute("""
            INSERT INTO complaints (customer_id, call_log_id, category, description)
            VALUES (?, ?, ?, ?)
        """, (data.get("customer_id"), c.lastrowid,
              data.get("complaint_category", "general"),
              data["complaint_details"]))

    conn.commit()
    conn.close()
    return {"status": "call_logged"}


@app.post("/api/agent/add_customer_phone")
async def agent_add_phone(request: Request):
    """Webhook tool: add phone number to customer."""
    data = await request.json()
    customer_id = data.get("customer_id")
    phone = data.get("phone_number", "").replace("+", "").replace(" ", "")
    person = data.get("contact_person", "unknown")

    if not customer_id or not phone:
        return {"status": "error", "message": "Customer ID and phone number required"}

    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM customer_contacts WHERE customer_id = ? AND phone_number = ?",
        (customer_id, phone)
    ).fetchone()

    if existing:
        conn.close()
        return {"status": "already_exists", "message": "This phone number is already registered for this customer"}

    conn.execute("""
        INSERT INTO customer_contacts (customer_id, contact_person, phone_number, added_by)
        VALUES (?, ?, ?, 'ai_agent')
    """, (customer_id, person.lower(), phone))
    conn.commit()
    conn.close()
    return {"status": "added", "message": f"Phone number {phone} added for {person}"}


@app.post("/api/agent/get_customer_orders")
async def agent_get_customer_orders(request: Request):
    """Webhook tool: get order history for a customer."""
    data = await request.json()
    customer_id = data.get("customer_id")
    product_query = data.get("product", "")
    limit = data.get("limit", 5)

    if not customer_id:
        return {"found": False, "message": "Customer ID required"}

    conn = get_db()

    query = """
        SELECT o.id, o.order_number, o.total_amount, o.status, o.delivery_schedule,
               o.created_at, o.notes
        FROM orders o
        WHERE o.customer_id = ? AND o.created_at >= '2026-05-12'
        ORDER BY o.created_at DESC LIMIT ?
    """
    orders = conn.execute(query, (customer_id, limit)).fetchall()

    if not orders:
        conn.close()
        if product_query:
            return {
                "found": False,
                "message": f"No previous orders found for {product_query}. This customer hasn't ordered before."
            }
        return {"found": False, "message": "No order history found for this customer."}

    order_list = []
    for o in orders:
        o_dict = dict(o)
        items = conn.execute("""
            SELECT oi.product_description, oi.quantity, oi.unit_price, oi.total_price,
                   oi.packing, oi.uom, p.category, p.brand
            FROM order_items oi
            LEFT JOIN products p ON p.id = oi.product_id
            WHERE oi.order_id = ?
        """, (o["id"],)).fetchall()
        o_dict["items"] = [dict(i) for i in items]
        order_list.append(o_dict)

    conn.close()

    if product_query:
        matching_items = []
        for order in order_list:
            for item in order["items"]:
                desc = (item.get("product_description") or "").lower()
                cat = (item.get("category") or "").lower()
                if product_query.lower() in desc or product_query.lower() in cat:
                    matching_items.append({
                        "product": item["product_description"],
                        "quantity": item["quantity"],
                        "price": item["unit_price"],
                        "packing": item["packing"],
                        "order_date": order["created_at"],
                        "order_number": order["order_number"]
                    })
        if matching_items:
            return {
                "found": True,
                "product_history": matching_items,
                "message": f"Found {len(matching_items)} past order(s) for {product_query}"
            }
        else:
            return {
                "found": False,
                "message": f"Customer has orders but never ordered {product_query} before."
            }

    return {
        "found": True,
        "order_count": len(order_list),
        "orders": order_list,
        "message": f"Found {len(order_list)} recent order(s)"
    }


def _get_wallet_balance():
    conn = get_db()
    result = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) as balance FROM wallet_transactions"
    ).fetchone()

    recent = conn.execute("""
        SELECT transaction_type, amount, description, created_at
        FROM wallet_transactions
        ORDER BY created_at DESC LIMIT 10
    """).fetchall()

    conn.close()

    balance = round(result["balance"], 2)
    return {
        "balance": balance,
        "recent_transactions": [dict(r) for r in recent],
        "message": f"Current wallet balance is {balance} riyals" if balance > 0 else "Wallet balance is 0. No credits available."
    }


@app.get("/api/agent/get_wallet_balance")
async def agent_get_wallet_balance_get():
    """Browser-friendly: get shared wallet balance."""
    return _get_wallet_balance()


@app.post("/api/agent/get_wallet_balance")
async def agent_get_wallet_balance(request: Request):
    """Webhook tool: get shared wallet balance (pool across all customers)."""
    return _get_wallet_balance()


@app.post("/api/agent/update_wallet")
async def agent_update_wallet(request: Request):
    """Webhook tool: add wallet transaction (credit/debit)."""
    data = await request.json()
    customer_id = data.get("customer_id")
    txn_type = data.get("transaction_type", "adjustment")
    amount = data.get("amount", 0)
    description = data.get("description", "")
    order_id = data.get("order_id")

    if not customer_id or amount == 0:
        return {"status": "error", "message": "Customer ID and non-zero amount required"}

    conn = get_db()
    conn.execute("""
        INSERT INTO wallet_transactions (customer_id, order_id, transaction_type, amount, description)
        VALUES (?, ?, ?, ?, ?)
    """, (customer_id, order_id, txn_type, amount, description))
    conn.commit()

    new_balance = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM wallet_transactions WHERE customer_id = ?",
        (customer_id,)
    ).fetchone()[0]
    conn.close()

    return {
        "status": "recorded",
        "new_balance": round(new_balance, 2),
        "message": f"Transaction recorded. New wallet balance: {round(new_balance, 2)} riyals"
    }


@app.post("/api/agent/update_customer")
async def agent_update_customer_data(request: Request):
    """Webhook tool: update customer calling time."""
    data = await request.json()
    customer_id = data.get("customer_id")

    if not customer_id:
        return {"status": "error", "message": "Customer ID required"}

    conn = get_db()
    updated_fields = []

    if "calling_time" in data:
        existing = conn.execute(
            "SELECT id FROM customer_call_schedule WHERE customer_id = ?",
            (customer_id,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE customer_call_schedule SET calling_time = ? WHERE customer_id = ?",
                (data["calling_time"], customer_id))
        else:
            conn.execute(
                "INSERT INTO customer_call_schedule (customer_id, calling_time) VALUES (?, ?)",
                (customer_id, data["calling_time"]))
        updated_fields.append("calling_time")

    if "rescheduled_time" in data:
        existing = conn.execute(
            "SELECT id FROM customer_call_schedule WHERE customer_id = ?",
            (customer_id,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE customer_call_schedule SET rescheduled_time = ? WHERE customer_id = ?",
                (data["rescheduled_time"], customer_id))
        else:
            conn.execute(
                "INSERT INTO customer_call_schedule (customer_id, calling_time, rescheduled_time) VALUES (?, '', ?)",
                (customer_id, data["rescheduled_time"]))
        updated_fields.append("rescheduled_time")

    conn.commit()
    conn.close()

    if not updated_fields:
        return {"status": "no_changes", "message": "No valid fields to update"}

    return {
        "status": "updated",
        "updated_fields": updated_fields,
        "message": f"Updated: {', '.join(updated_fields)}"
    }
