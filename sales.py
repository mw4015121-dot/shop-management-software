
from datetime import datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database import get_connection

router = APIRouter(prefix="/sales", tags=["Sales / POS"])


def create_sales_tables():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INT AUTO_INCREMENT PRIMARY KEY,
                invoice_no VARCHAR(50) NOT NULL UNIQUE,
                customer_id INT NULL,
                sale_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                subtotal DECIMAL(12,2) NOT NULL DEFAULT 0,
                discount DECIMAL(12,2) NOT NULL DEFAULT 0,
                grand_total DECIMAL(12,2) NOT NULL DEFAULT 0,
                paid_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
                due_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
                payment_method VARCHAR(30) NOT NULL DEFAULT 'Cash',
                notes TEXT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'Completed'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sale_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sale_id INT NOT NULL,
                product_id INT NOT NULL,
                product_name VARCHAR(255) NOT NULL,
                quantity DECIMAL(12,3) NOT NULL,
                unit_price DECIMAL(12,2) NOT NULL,
                line_total DECIMAL(12,2) NOT NULL,
                INDEX idx_sale_id (sale_id),
                INDEX idx_product_id (product_id)
            )
        """)

        connection.commit()
    finally:
        cursor.close()
        connection.close()


class SaleItemInput(BaseModel):
    product_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0)


class SaleCreate(BaseModel):
    customer_id: int | None = None
    items: list[SaleItemInput] = Field(min_length=1)
    discount: Decimal = Field(default=Decimal("0"), ge=0)
    paid_amount: Decimal = Field(default=Decimal("0"), ge=0)
    payment_method: Literal[
        "Cash", "Easypaisa", "JazzCash", "NayaPay", "Bank", "Other"
    ] = "Cash"
    notes: str | None = None


@router.post("/setup")
def setup_sales_tables():
    create_sales_tables()
    return {
        "success": True,
        "message": "Sales tables are ready"
    }


@router.post("/")
def create_sale(sale: SaleCreate):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        connection.start_transaction()

        if sale.customer_id is not None:
            cursor.execute(
                "SELECT id FROM customers WHERE id = %s FOR UPDATE",
                (sale.customer_id,)
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Customer not found")

        # Combine duplicate product IDs into one quantity.
        quantities = {}
        for item in sale.items:
            quantities[item.product_id] = (
                quantities.get(item.product_id, Decimal("0"))
                + item.quantity
            )

        subtotal = Decimal("0")
        prepared_items = []

        # Lock products so concurrent sales cannot oversell stock.
        for product_id, quantity in quantities.items():
            cursor.execute("""
                SELECT id, product_name, final_price, stock_quantity
                FROM products
                WHERE id = %s
                FOR UPDATE
            """, (product_id,))

            product = cursor.fetchone()

            if not product:
                raise HTTPException(
                    status_code=404,
                    detail=f"Product ID {product_id} not found"
                )

            price = Decimal(str(product["final_price"]))
            stock = Decimal(str(product["stock_quantity"]))

            if stock < quantity:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Insufficient stock for {product['product_name']}. "
                        f"Available: {stock}, requested: {quantity}"
                    )
                )

            line_total = (price * quantity).quantize(Decimal("0.01"))
            subtotal += line_total

            prepared_items.append({
                "product_id": product_id,
                "product_name": product["product_name"],
                "quantity": quantity,
                "unit_price": price,
                "line_total": line_total
            })

        subtotal = subtotal.quantize(Decimal("0.01"))
        discount = sale.discount.quantize(Decimal("0.01"))

        if discount > subtotal:
            raise HTTPException(
                status_code=400,
                detail="Discount cannot exceed subtotal"
            )

        grand_total = (subtotal - discount).quantize(Decimal("0.01"))

        if sale.paid_amount > grand_total:
            raise HTTPException(
                status_code=400,
                detail="Paid amount cannot exceed grand total"
            )

        paid_amount = sale.paid_amount.quantize(Decimal("0.01"))
        due_amount = (grand_total - paid_amount).quantize(Decimal("0.01"))

        invoice_no = (
            "INV-" + datetime.now().strftime("%Y%m%d%H%M%S%f")
        )

        cursor.execute("""
            INSERT INTO sales (
                invoice_no, customer_id, subtotal, discount,
                grand_total, paid_amount, due_amount,
                payment_method, notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            invoice_no,
            sale.customer_id,
            subtotal,
            discount,
            grand_total,
            paid_amount,
            due_amount,
            sale.payment_method,
            sale.notes
        ))

        sale_id = cursor.lastrowid

        for item in prepared_items:
            cursor.execute("""
                INSERT INTO sale_items (
                    sale_id, product_id, product_name,
                    quantity, unit_price, line_total
                )
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                sale_id,
                item["product_id"],
                item["product_name"],
                item["quantity"],
                item["unit_price"],
                item["line_total"]
            ))

            cursor.execute("""
                UPDATE products
                SET stock_quantity = stock_quantity - %s
                WHERE id = %s
            """, (item["quantity"], item["product_id"]))

        connection.commit()

        return {
            "success": True,
            "message": "Sale created successfully",
            "sale_id": sale_id,
            "invoice_no": invoice_no,
            "subtotal": float(subtotal),
            "discount": float(discount),
            "grand_total": float(grand_total),
            "paid_amount": float(paid_amount),
            "due_amount": float(due_amount)
        }

    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


@router.get("/")
def get_sales(search: str = "", page: int = 1, limit: int = 20):
    page = max(page, 1)
    limit = min(max(limit, 1), 100)
    offset = (page - 1) * limit
    search = search.strip()

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        pattern = f"%{search}%"

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            WHERE %s = ''
               OR s.invoice_no LIKE %s
               OR CAST(s.id AS CHAR) LIKE %s
               OR c.customer_name LIKE %s
        """, (search, pattern, pattern, pattern))

        total = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT s.*, c.customer_name
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            WHERE %s = ''
               OR s.invoice_no LIKE %s
               OR CAST(s.id AS CHAR) LIKE %s
               OR c.customer_name LIKE %s
            ORDER BY s.id DESC
            LIMIT %s OFFSET %s
        """, (search, pattern, pattern, pattern, limit, offset))

        records = cursor.fetchall()

        for record in records:
            if record.get("sale_date"):
                record["sale_date"] = record["sale_date"].isoformat()
            for key in (
                "subtotal", "discount", "grand_total",
                "paid_amount", "due_amount"
            ):
                record[key] = float(record[key])

        return {
            "success": True,
            "sales": records,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit
        }
    finally:
        cursor.close()
        connection.close()


@router.get("/{sale_id}")
def get_sale(sale_id: int):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT s.*, c.customer_name
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            WHERE s.id = %s
        """, (sale_id,))

        sale = cursor.fetchone()

        if not sale:
            raise HTTPException(status_code=404, detail="Sale not found")

        cursor.execute("""
            SELECT id, product_id, product_name,
                   quantity, unit_price, line_total
            FROM sale_items
            WHERE sale_id = %s
            ORDER BY id
        """, (sale_id,))

        sale["items"] = cursor.fetchall()

        if sale.get("sale_date"):
            sale["sale_date"] = sale["sale_date"].isoformat()

        for key in (
            "subtotal", "discount", "grand_total",
            "paid_amount", "due_amount"
        ):
            sale[key] = float(sale[key])

        for item in sale["items"]:
            for key in ("quantity", "unit_price", "line_total"):
                item[key] = float(item[key])

        return {"success": True, "sale": sale}
    finally:
        cursor.close()
        connection.close()
