
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database import get_connection

router = APIRouter(prefix="/sales-returns", tags=["Sales Returns"])


def create_sales_return_tables():
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales_returns (
                id INT AUTO_INCREMENT PRIMARY KEY,
                return_no VARCHAR(60) NOT NULL UNIQUE,
                sale_id INT NOT NULL,
                customer_id INT NULL,
                refund_method VARCHAR(30) NOT NULL,
                return_total DECIMAL(12,2) NOT NULL DEFAULT 0,
                notes TEXT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_return_sale (sale_id),
                INDEX idx_return_customer (customer_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales_return_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                return_id INT NOT NULL,
                sale_item_id INT NOT NULL,
                product_id INT NOT NULL,
                product_name VARCHAR(255) NOT NULL,
                quantity DECIMAL(12,3) NOT NULL,
                unit_price DECIMAL(12,2) NOT NULL,
                line_total DECIMAL(12,2) NOT NULL,
                INDEX idx_return_item (return_id),
                INDEX idx_original_sale_item (sale_item_id)
            )
        """)

        # Credit ledger: customer credit is recorded separately.
        # It does not automatically change customers.total_paid/due.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customer_credit_transactions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                customer_id INT NOT NULL,
                return_id INT NOT NULL,
                amount DECIMAL(12,2) NOT NULL,
                transaction_type VARCHAR(30) NOT NULL DEFAULT 'Return Credit',
                description VARCHAR(255) NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_credit_return (return_id),
                INDEX idx_credit_customer (customer_id)
            )
        """)
        connection.commit()
    finally:
        cursor.close()
        connection.close()


class ReturnItemInput(BaseModel):
    sale_item_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0)


class SaleReturnInput(BaseModel):
    sale_id: int = Field(gt=0)
    refund_method: Literal["Cash", "Customer Credit"]
    items: list[ReturnItemInput] = Field(min_length=1)
    notes: str | None = None


def as_money(value):
    return Decimal(str(value or 0)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def setup_tables_if_needed():
    create_sales_return_tables()


@router.post("/setup")
def setup_sales_returns():
    create_sales_return_tables()
    return {"success": True, "message": "Sales Return tables are ready"}


@router.get("/sale/{sale_id}")
def get_sale_for_return(sale_id: int):
    setup_tables_if_needed()
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
            cursor.execute(
                "SELECT id, invoice_no FROM sales WHERE invoice_no = %s",
                (str(sale_id),)
            )
            sale = cursor.fetchone()

        if not sale:
            raise HTTPException(status_code=404, detail="Sale / invoice not found")

        cursor.execute("""
            SELECT
                si.id AS sale_item_id,
                si.product_id,
                si.product_name,
                si.quantity AS sold_quantity,
                si.unit_price,
                si.line_total,
                COALESCE((
                    SELECT SUM(sri.quantity)
                    FROM sales_return_items sri
                    WHERE sri.sale_item_id = si.id
                ), 0) AS returned_quantity
            FROM sale_items si
            WHERE si.sale_id = %s
            ORDER BY si.id
        """, (sale["id"],))
        items = cursor.fetchall()

        for item in items:
            sold = Decimal(str(item["sold_quantity"]))
            returned = Decimal(str(item["returned_quantity"]))
            item["sold_quantity"] = float(sold)
            item["returned_quantity"] = float(returned)
            item["remaining_quantity"] = float(max(Decimal("0"), sold - returned))
            item["unit_price"] = float(item["unit_price"])
            item["line_total"] = float(item["line_total"])

        for key in ("subtotal", "discount", "grand_total", "paid_amount", "due_amount"):
            if key in sale and sale[key] is not None:
                sale[key] = float(sale[key])

        if sale.get("sale_date"):
            sale["sale_date"] = sale["sale_date"].isoformat()

        sale["items"] = items
        return {"success": True, "sale": sale}
    finally:
        cursor.close()
        connection.close()


@router.post("/")
def create_sales_return(data: SaleReturnInput):
    create_sales_return_tables()
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        connection.start_transaction()

        cursor.execute("""
            SELECT id, invoice_no, customer_id
            FROM sales
            WHERE id = %s
            FOR UPDATE
        """, (data.sale_id,))
        sale = cursor.fetchone()

        if not sale:
            raise HTTPException(status_code=404, detail="Sale not found")

        if data.refund_method == "Customer Credit" and not sale["customer_id"]:
            raise HTTPException(
                status_code=400,
                detail="Customer Credit requires a sale linked to a registered customer."
            )

        # Combine duplicate sale item IDs.
        quantities = {}
        for item in data.items:
            quantities[item.sale_item_id] = (
                quantities.get(item.sale_item_id, Decimal("0")) + item.quantity
            )

        prepared = []
        return_total = Decimal("0.00")

        for sale_item_id, quantity in quantities.items():
            cursor.execute("""
                SELECT si.id, si.sale_id, si.product_id, si.product_name,
                       si.quantity, si.unit_price
                FROM sale_items si
                WHERE si.id = %s AND si.sale_id = %s
                FOR UPDATE
            """, (sale_item_id, data.sale_id))
            original = cursor.fetchone()

            if not original:
                raise HTTPException(
                    status_code=400,
                    detail=f"Sale item {sale_item_id} does not belong to this sale."
                )

            sold_quantity = Decimal(str(original["quantity"]))

            cursor.execute("""
                SELECT COALESCE(SUM(quantity), 0) AS returned
                FROM sales_return_items
                WHERE sale_item_id = %s
                FOR UPDATE
            """, (sale_item_id,))
            already_returned = Decimal(str(cursor.fetchone()["returned"] or 0))

            remaining = sold_quantity - already_returned
            if quantity > remaining:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"{original['product_name']}: only {remaining} "
                        "quantity remains eligible for return."
                    )
                )

            unit_price = as_money(original["unit_price"])
            line_total = as_money(unit_price * quantity)
            return_total += line_total

            cursor.execute("""
                SELECT id
                FROM products
                WHERE id = %s
                FOR UPDATE
            """, (original["product_id"],))
            if not cursor.fetchone():
                raise HTTPException(
                    status_code=404,
                    detail=f"Product {original['product_name']} no longer exists."
                )

            prepared.append({
                "sale_item_id": sale_item_id,
                "product_id": original["product_id"],
                "product_name": original["product_name"],
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": line_total
            })

        return_total = as_money(return_total)
        if return_total <= 0:
            raise HTTPException(status_code=400, detail="Return total must be greater than zero.")

        return_no = "RET-" + datetime.now().strftime("%Y%m%d%H%M%S%f")

        cursor.execute("""
            INSERT INTO sales_returns (
                return_no, sale_id, customer_id, refund_method, return_total, notes
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            return_no,
            data.sale_id,
            sale["customer_id"],
            data.refund_method,
            return_total,
            data.notes
        ))
        return_id = cursor.lastrowid

        for item in prepared:
            cursor.execute("""
                INSERT INTO sales_return_items (
                    return_id, sale_item_id, product_id, product_name,
                    quantity, unit_price, line_total
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                return_id,
                item["sale_item_id"],
                item["product_id"],
                item["product_name"],
                item["quantity"],
                item["unit_price"],
                item["line_total"]
            ))

            cursor.execute("""
                UPDATE products
                SET stock_quantity = stock_quantity + %s
                WHERE id = %s
            """, (item["quantity"], item["product_id"]))

        if data.refund_method == "Customer Credit":
            cursor.execute("""
                INSERT INTO customer_credit_transactions (
                    customer_id, return_id, amount, transaction_type, description
                )
                VALUES (%s, %s, %s, 'Return Credit', %s)
            """, (
                sale["customer_id"],
                return_id,
                return_total,
                f"Credit for return {return_no}"
            ))

        connection.commit()
        return {
            "success": True,
            "message": "Sales return saved successfully",
            "return_id": return_id,
            "return_no": return_no,
            "sale_id": data.sale_id,
            "invoice_no": sale["invoice_no"],
            "refund_method": data.refund_method,
            "return_total": float(return_total),
            "customer_id": sale["customer_id"]
        }

    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


@router.get("/")
def get_sales_returns(search: str = "", page: int = 1, limit: int = 50):
    create_sales_return_tables()
    page = max(page, 1)
    limit = min(max(limit, 1), 100)
    offset = (page - 1) * limit
    search = search.strip()
    pattern = f"%{search}%"

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM sales_returns sr
            JOIN sales s ON s.id = sr.sale_id
            LEFT JOIN customers c ON c.id = sr.customer_id
            WHERE %s = ''
               OR sr.return_no LIKE %s
               OR s.invoice_no LIKE %s
               OR CAST(sr.sale_id AS CHAR) LIKE %s
               OR c.customer_name LIKE %s
        """, (search, pattern, pattern, pattern, pattern))
        total = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT sr.*, s.invoice_no, c.customer_name
            FROM sales_returns sr
            JOIN sales s ON s.id = sr.sale_id
            LEFT JOIN customers c ON c.id = sr.customer_id
            WHERE %s = ''
               OR sr.return_no LIKE %s
               OR s.invoice_no LIKE %s
               OR CAST(sr.sale_id AS CHAR) LIKE %s
               OR c.customer_name LIKE %s
            ORDER BY sr.id DESC
            LIMIT %s OFFSET %s
        """, (search, pattern, pattern, pattern, pattern, limit, offset))
        rows = cursor.fetchall()

        for row in rows:
            row["return_total"] = float(row["return_total"])
            if row.get("created_at"):
                row["created_at"] = row["created_at"].isoformat()

        return {
            "success": True,
            "returns": rows,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit
        }
    finally:
        cursor.close()
        connection.close()


@router.get("/{return_id}")
def get_sales_return(return_id: int):
    create_sales_return_tables()
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT sr.*, s.invoice_no, c.customer_name
            FROM sales_returns sr
            JOIN sales s ON s.id = sr.sale_id
            LEFT JOIN customers c ON c.id = sr.customer_id
            WHERE sr.id = %s
        """, (return_id,))
        record = cursor.fetchone()
        if not record:
            raise HTTPException(status_code=404, detail="Return not found")

        cursor.execute("""
            SELECT product_name, quantity, unit_price, line_total
            FROM sales_return_items
            WHERE return_id = %s
            ORDER BY id
        """, (return_id,))
        record["items"] = cursor.fetchall()

        record["return_total"] = float(record["return_total"])
        for item in record["items"]:
            for key in ("quantity", "unit_price", "line_total"):
                item[key] = float(item[key])

        if record.get("created_at"):
            record["created_at"] = record["created_at"].isoformat()

        return {"success": True, "return": record}
    finally:
        cursor.close()
        connection.close()
