
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from database import get_connection
from products import router as products_router
from customers import router as customers_router
from auth import router as auth_router
from suppliers import router as suppliers_router
from purchases import router as purchases_router
from sales import router as sales_router
from sales_returns import router as sales_returns_router
from inventory import router as inventory_router
from expenses import router as expenses_router
from staff import router as staff_router
from payments import router as payments_router


# Project folders
BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "uploads"
FRONTEND_DIR = BASE_DIR / "frontend"

# Create uploads folder if it does not exist
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


# Create FastAPI application
app = FastAPI(
    title="Shop Management Software",
    version="1.0.0"
)


# Session Security
secret_key = os.environ.get("SHOP_SESSION_SECRET")

if not secret_key:
    raise RuntimeError(
        "SHOP_SESSION_SECRET environment variable is not set."
    )

app.add_middleware(
    SessionMiddleware,
    secret_key=secret_key,
    same_site="lax",
    https_only=False
)


# API Routers
app.include_router(products_router)
app.include_router(customers_router)
app.include_router(auth_router)
app.include_router(suppliers_router)
app.include_router(purchases_router)
app.include_router(sales_router)
app.include_router(sales_returns_router)
app.include_router(inventory_router)
app.include_router(expenses_router)
app.include_router(staff_router)
app.include_router(payments_router)


# Product Images
app.mount(
    "/uploads",
    StaticFiles(directory=str(UPLOADS_DIR)),
    name="uploads"
)


# Frontend Files
app.mount(
    "/frontend",
    StaticFiles(directory=str(FRONTEND_DIR), html=True),
    name="frontend"
)


# Home Page
@app.get("/")
def home():
    return RedirectResponse(
        url="/frontend/login.html",
        status_code=302
    )


# Database Connection Test
@app.get("/test-db")
def test_database():
    connection = get_connection()

    try:
        return {
            "success": True,
            "message": "MySQL Database Connected Successfully"
        }
    finally:
        connection.close()


# Application Health Check
@app.get("/health")
def health_check():
    return {
        "success": True,
        "message": "Shop Management Software is Running"
    }
