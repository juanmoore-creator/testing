from fastapi import FastAPI, Header, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from typing import Optional, List
import datetime

app = FastAPI()

# Almacén de logs (en memoria para testing)
request_history = []

# --- MIDDLEWARE PARA CAPTURAR SOLICITUDES ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Capturamos metadatos de la solicitud
    method = request.method
    path = request.url.path
    
    # Procesamos la solicitud
    response = await call_next(request)
    
    # Guardamos en el historial (solo si es de la API)
    if path.startswith("/api/"):
        log_entry = {
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "method": method,
            "path": path,
            "status": response.status_code
        }
        # Insertar al inicio para ver lo más reciente primero
        request_history.insert(0, log_entry)
        if len(request_history) > 50: # Limite de logs
            request_history.pop()
            
    return response

# --- RUTA DEL DASHBOARD ---
@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    # Construcción simple de HTML/CSS
    rows = "".join([
        f"<tr><td>{log['time']}</td><td><span class='badge {log['method']}'>{log['method']}</span></td><td>{log['path']}</td><td>{log['status']}</td></tr>"
        for log in request_history
    ])
    
    html_content = f"""
    <html>
        <head>
            <title>APER Mock Dashboard</title>
            <style>
                body {{ font-family: sans-serif; margin: 40px; background: #f4f7f6; }}
                table {{ width: 100%; border-collapse: collapse; background: white; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #004a99; color: white; }}
                .GET {{ color: green; font-weight: bold; }}
                .POST {{ color: blue; font-weight: bold; }}
                .PUT {{ color: orange; font-weight: bold; }}
                .badge {{ padding: 4px 8px; border-radius: 4px; font-size: 0.8em; }}
                h1 {{ color: #333; }}
            </style>
        </head>
        <body>
            <h1>APER API Simulator - Registro de Actividad</h1>
            <p>Monitoreo de sincronización ERP Bridge vs APER</p>
            <table>
                <thead>
                    <tr><th>Fecha/Hora</th><th>Método</th><th>Endpoint</th><th>Estado</th></tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
            <script>setTimeout(() => location.reload(), 5000);</script>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# --- TUS ENDPOINTS ORIGINALES DE APER AQUÍ ---
# Ej: GET /api/products, PUT /api/products, etc.

# --- BASE DE DATOS MOCK ---
db = {
    "products": [
        {"id": 77180, "reference": "01.01.0001", "price": "1500.00", "quantity": "10", "id_category_default": "2", "active": "1"},
        {"id": 77181, "reference": "02.07.0283", "price": "2500.00", "quantity": "5", "id_category_default": "2", "active": "1"}
    ],
    "orders": [
        {
            "id": 1234, "current_state": "6", "total_paid": "0.90", 
            "associations": {"order_rows": [{"product_id": "77180", "product_reference": "01.01.0001", "product_quantity": "1"}]}
        }
    ],
    "specific_prices": [{"id": 16826, "id_product": "77180", "reduction": "0.100000", "reduction_type": "percentage"}],
    "combinations": [{"id": 8968, "id_product": "77181", "reference": "prueba", "quantity": "11"}],
    "order_states": [{"id": 6, "name": "Cancelado", "template": "order_canceled"}]
}

# --- MIDDLEWARE DE SEGURIDAD ---
def validate_request(auth: str, content_type: str):
    if not auth or "Basic" not in auth:
        raise HTTPException(status_code=401, detail="Missing Authorization Header [cite: 289]")
    if content_type != "application/json":
        raise HTTPException(status_code=415, detail="Content-Type must be application/json ")

# --- ENDPOINTS: PRODUCTOS ---
@app.get("/api/products")
async def get_products(authorization: str = Header(None), content_type: str = Header(None), reference: Optional[str] = Query(None, alias="filter[reference]")):
    validate_request(authorization, content_type)
    if reference:
        return {"products": [p for p in db["products"] if p["reference"] == reference]} # [cite: 404]
    return {"products": [{"id": str(p["id"])} for p in db["products"]]} # [cite: 399]

@app.post("/api/products")
async def create_product(payload: dict, authorization: str = Header(None), content_type: str = Header(None)):
    validate_request(authorization, content_type)
    data = payload.get("product", {})
    if data.get("id_category_default") != "2" or not data.get("reference"):
        raise HTTPException(status_code=400, detail="Faltan campos obligatorios: id_category_default=2 y reference ")
    new_id = max([p["id"] for p in db["products"]]) + 1
    data["id"] = new_id
    db["products"].append(data)
    return {"product": data} # [cite: 495]

@app.put("/api/products")
async def update_product(payload: dict, authorization: str = Header(None), content_type: str = Header(None)):
    validate_request(authorization, content_type)
    p_data = payload.get("product", {})
    # Regla: Reference debe coincidir con el original para actualizar [cite: 444]
    return {"message": "Update successful", "id": p_data.get("id")}

# --- ENDPOINTS: PEDIDOS (ORDERS) ---
@app.get("/api/orders")
async def list_orders(authorization: str = Header(None), content_type: str = Header(None)):
    validate_request(authorization, content_type)
    return {"orders": [{"id": str(o["id"])} for o in db["orders"]]} # [cite: 559]

@app.get("/api/orders/{id}")
async def order_detail(id: int, authorization: str = Header(None), content_type: str = Header(None)):
    validate_request(authorization, content_type)
    order = next((o for o in db["orders"] if o["id"] == id), None)
    if not order: raise HTTPException(status_code=404)
    return {"order": order} # [cite: 565]

@app.put("/api/orders/{id}")
async def update_order_state(id: int, payload: dict, authorization: str = Header(None), content_type: str = Header(None)):
    validate_request(authorization, content_type)
    new_state = payload.get("order", {}).get("current_state") # 
    return {"message": f"Order {id} state updated to {new_state}"}

# --- ENDPOINTS: PRECIOS ESPECÍFICOS Y VARIANTES ---
@app.get("/api/specific_prices")
async def get_prices(authorization: str = Header(None), content_type: str = Header(None)):
    validate_request(authorization, content_type)
    return {"specific_prices": db["specific_prices"]} # [cite: 779]

@app.post("/api/combinations")
async def create_combination(payload: dict, authorization: str = Header(None), content_type: str = Header(None)):
    validate_request(authorization, content_type)
    data = payload.get("combination", {})
    if not data.get("id_product"):
        raise HTTPException(status_code=400, detail="Debe especificar id_product [cite: 911]")
    return {"combination": data}

@app.get("/api/order_states/{id}")
async def get_state(id: int, authorization: str = Header(None), content_type: str = Header(None)):
    validate_request(authorization, content_type)
    state = next((s for s in db["order_states"] if s["id"] == id), None)
    return {"order_state": state} # [cite: 727]
