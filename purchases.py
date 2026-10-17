from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

import mysql.connector
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from database import get_connection


router = APIRouter(prefix="/purchases", tags=["Purchases"])


# =========================
# Pydantic Models
# =========================

class PurchaseItem(BaseModel):
    product_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    purchase_price: Decimal = Field(ge=0)
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0)


class PurchaseCreate(BaseModel):
    purchase_code: str = Field(min_length=1, max_length=100)
    supplier_id: int = Field(gt=0)
    supplier_invoice_no: Optional[str] = None
    purchase_date: date = Field(default_factory=date.today)
    items: list[PurchaseItem] = Field(min_length=1)
    paid_amount: Decimal = Field(default=Decimal("0"), ge=0)
    payment_method: str = "cash"
    extra_charges: Decimal = Field(default=Decimal("0"), ge=0)
    notes: Optional[str] = None


# =========================
# Helper Functions
# =========================

def money(value):
    return Decimal(str(value or 0)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


def calculate_purchase(items, extra_charges=0):
    subtotal = Decimal("0")
    discount_total = Decimal("0")
    tax_total = Decimal("0")

    for item in items:
        quantity = Decimal(str(item.quantity))
        price = Decimal(str(item.purchase_price))
        discount = Decimal(str(item.discount_amount or 0))
        tax = Decimal(str(item.tax_amount or 0))

        line_subtotal = quantity * price

        if discount > line_subtotal:
            raise HTTPException(
                status_code=400,
                detail="Discount cannot exceed item subtotal."
            )

        taxable_amount = line_subtotal - discount

        subtotal += line_subtotal
        discount_total += discount
        tax_total += tax

        if tax < 0:
            raise HTTPException(
                status_code=400,
                detail="Tax amount cannot be negative."
            )

    total = (
        subtotal
        - discount_total
        + tax_total
        + Decimal(str(extra_charges or 0))
    )

    return {
        "subtotal": money(subtotal),
        "discount_amount": money(discount_total),
        "tax_amount": money(tax_total),
        "extra_charges": money(extra_charges),
        "total_amount": money(total),
    }


def get_payment_status(total, paid):
    if paid <= 0:
        return "unpaid"
    elif paid >= total:
        return "paid"
    return "partial"


def get_connection_cursor():
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    return connection, cursor


def check_supplier(cursor, supplier_id):
    cursor.execute(
        "SELECT id, status FROM suppliers WHERE id = %s",
        (supplier_id,)
    )
    supplier = cursor.fetchone()

    if not supplier:
        raise HTTPException(
            status_code=404,
            detail="Supplier not found."
        )

    if supplier.get("status") and supplier["status"].lower() != "active":
        raise HTTPException(
            status_code=400,
            detail="Supplier is inactive."
        )


def lock_products(cursor, items):
    product_ids = list(set(item.product_id for item in items))

    if not product_ids:
        raise HTTPException(
            status_code=400,
            detail="At least one product is required."
        )

    placeholders = ",".join(["%s"] * len(product_ids))

    cursor.execute(
        f"""
        SELECT id, product_name, purchase_price, stock_quantity
        FROM products
        WHERE id IN ({placeholders})
        FOR UPDATE
        """,
        tuple(product_ids)
    )

    products = cursor.fetchall()
    product_map = {product["id"]: product for product in products}

    for product_id in product_ids:
        if product_id not in product_map:
            raise HTTPException(
                status_code=404,
                detail=f"Product ID {product_id} not found."
            )

    return product_map


def combine_quantities(items):
    quantities = {}

    for item in items:
        quantities[item.product_id] = (
            quantities.get(item.product_id, Decimal("0"))
            + Decimal(str(item.quantity))
        )

    return quantities


def update_stock(cursor, items, direction):
    quantities = combine_quantities(items)

    for product_id, quantity in quantities.items():
        if direction < 0:
            cursor.execute(
                """
                SELECT stock_quantity
                FROM products
                WHERE id = %s
                FOR UPDATE
                """,
                (product_id,)
            )

            product = cursor.fetchone()

            if not product:
                raise HTTPException(
                    status_code=404,
                    detail=f"Product ID {product_id} not found."
                )

            current_stock = Decimal(
                str(product.get("stock_quantity") or 0)
            )

            if current_stock < quantity:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Cannot remove purchase stock for product "
                        f"{product_id}. Current stock is insufficient."
                    )
                )

        cursor.execute(
            """
            UPDATE products
            SET stock_quantity = COALESCE(stock_quantity, 0) + %s
            WHERE id = %s
            """,
            (quantity * direction, product_id)
        )


def save_purchase_items(cursor, purchase_id, items):
    for item in items:
        line_subtotal = (
            Decimal(str(item.quantity))
            * Decimal(str(item.purchase_price))
        )

        line_total = (
            line_subtotal
            - Decimal(str(item.discount_amount or 0))
            + Decimal(str(item.tax_amount or 0))
        )

        if line_total < 0:
            raise HTTPException(
                status_code=400,
                detail="Purchase item total cannot be negative."
            )

        cursor.execute(
            """
            INSERT INTO purchase_items (
                purchase_id,
                product_id,
                quantity,
                purchase_price,
                discount_amount,
                tax_amount,
                total_amount
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                purchase_id,
                item.product_id,
                item.quantity,
                item.purchase_price,
                item.discount_amount,
                item.tax_amount,
                money(line_total)
            )
        )

        cursor.execute(
            """
            UPDATE products
            SET purchase_price = %s
            WHERE id = %s
            """,
            (item.purchase_price, item.product_id)
        )


def fetch_purchase(cursor, purchase_id):
    cursor.execute(
        """
        SELECT
            p.*,
            s.supplier_name
        FROM purchases p
        LEFT JOIN suppliers s ON s.id = p.supplier_id
        WHERE p.id = %s
        """,
        (purchase_id,)
    )

    purchase = cursor.fetchone()

    if not purchase:
        raise HTTPException(
            status_code=404,
            detail="Purchase not found."
        )

    cursor.execute(
        """
        SELECT
            pi.*,
            pr.product_name,
            pr.product_code
        FROM purchase_items pi
        LEFT JOIN products pr ON pr.id = pi.product_id
        WHERE pi.purchase_id = %s
        ORDER BY pi.id
        """,
        (purchase_id,)
    )

    purchase["items"] = cursor.fetchall()
    return purchase


# =========================
# GET All Purchases
# =========================

@router.get("/")
def get_purchases(
    search: Optional[str] = Query(default=None),
    supplier_id: Optional[int] = Query(default=None, gt=0),
    payment_status: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100)
):
    connection = None
    cursor = None

    try:
        connection, cursor = get_connection_cursor()

        conditions = []
        params = []

        if search:
            search_value = f"%{search}%"
            conditions.append(
                """
                (
                    p.purchase_code LIKE %s
                    OR p.supplier_invoice_no LIKE %s
                    OR s.supplier_name LIKE %s
                )
                """
            )
            params.extend([
                search_value,
                search_value,
                search_value
            ])

        if supplier_id:
            conditions.append("p.supplier_id = %s")
            params.append(supplier_id)

        if payment_status:
            conditions.append("p.payment_status = %s")
            params.append(payment_status)

        if status:
            conditions.append("p.status = %s")
            params.append(status)

        where_clause = ""

        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        cursor.execute(
            f"""
            SELECT COUNT(*) AS total
            FROM purchases p
            LEFT JOIN suppliers s ON s.id = p.supplier_id
            {where_clause}
            """,
            tuple(params)
        )

        total = cursor.fetchone()["total"]
        offset = (page - 1) * limit

        cursor.execute(
            f"""
            SELECT
                p.*,
                s.supplier_name
            FROM purchases p
            LEFT JOIN suppliers s ON s.id = p.supplier_id
            {where_clause}
            ORDER BY p.id DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params + [limit, offset])
        )

        purchases = cursor.fetchall()

        return {
            "success": True,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit,
            "data": purchases
        }

    except HTTPException:
        raise
    except mysql.connector.Error as error:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {error}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# =========================
# GET Purchase By ID
# =========================

@router.get("/{purchase_id}")
def get_purchase(purchase_id: int):
    connection = None
    cursor = None

    try:
        connection, cursor = get_connection_cursor()
        purchase = fetch_purchase(cursor, purchase_id)

        return {
            "success": True,
            "data": purchase
        }

    except HTTPException:
        raise
    except mysql.connector.Error as error:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {error}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# =========================
# CREATE Purchase
# =========================

@router.post("/")
def create_purchase(purchase: PurchaseCreate):
    connection = None
    cursor = None

    try:
        connection, cursor = get_connection_cursor()

        check_supplier(cursor, purchase.supplier_id)

        cursor.execute(
            "SELECT id FROM purchases WHERE purchase_code = %s",
            (purchase.purchase_code,)
        )

        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail="Purchase code already exists."
            )

        product_map = lock_products(cursor, purchase.items)

        totals = calculate_purchase(
            purchase.items,
            purchase.extra_charges
        )

        paid_amount = money(purchase.paid_amount)
        total_amount = totals["total_amount"]

        if paid_amount > total_amount:
            raise HTTPException(
                status_code=400,
                detail="Paid amount cannot exceed purchase total."
            )

        due_amount = money(total_amount - paid_amount)
        payment_status = get_payment_status(
            total_amount,
            paid_amount
        )

        cursor.execute(
            """
            INSERT INTO purchases (
                purchase_code,
                supplier_id,
                supplier_invoice_no,
                purchase_date,
                subtotal,
                discount_amount,
                tax_amount,
                extra_charges,
                total_amount,
                paid_amount,
                due_amount,
                payment_status,
                payment_method,
                notes,
                status
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            """,
            (
                purchase.purchase_code,
                purchase.supplier_id,
                purchase.supplier_invoice_no,
                purchase.purchase_date,
                totals["subtotal"],
                totals["discount_amount"],
                totals["tax_amount"],
                totals["extra_charges"],
                total_amount,
                paid_amount,
                due_amount,
                payment_status,
                purchase.payment_method,
                purchase.notes,
                "completed"
            )
        )

        purchase_id = cursor.lastrowid

        save_purchase_items(
            cursor,
            purchase_id,
            purchase.items
        )

        update_stock(cursor, purchase.items, 1)

        connection.commit()

        return {
            "success": True,
            "message": "Purchase saved and stock updated successfully",
            "purchase_id": purchase_id,
            "purchase_code": purchase.purchase_code,
            "subtotal": float(totals["subtotal"]),
            "discount_amount": float(totals["discount_amount"]),
            "tax_amount": float(totals["tax_amount"]),
            "extra_charges": float(totals["extra_charges"]),
            "total_amount": float(total_amount),
            "paid_amount": float(paid_amount),
            "due_amount": float(due_amount),
            "payment_status": payment_status
        }

    except HTTPException:
        if connection:
            connection.rollback()
        raise
    except mysql.connector.Error as error:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {error}"
        )
    except Exception as error:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# =========================
# UPDATE Purchase
# =========================

@router.put("/{purchase_id}")
def update_purchase(
    purchase_id: int,
    purchase: PurchaseCreate
):
    connection = None
    cursor = None

    try:
        connection, cursor = get_connection_cursor()

        cursor.execute(
            """
            SELECT *
            FROM purchases
            WHERE id = %s
            FOR UPDATE
            """,
            (purchase_id,)
        )

        old_purchase = cursor.fetchone()

        if not old_purchase:
            raise HTTPException(
                status_code=404,
                detail="Purchase not found."
            )

        if old_purchase["status"] == "cancelled":
            raise HTTPException(
                status_code=400,
                detail="Cancelled purchase cannot be updated."
            )

        old_paid_amount = money(old_purchase["paid_amount"])

        if money(purchase.paid_amount) != old_paid_amount:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Paid amount cannot be changed through this endpoint. "
                    "Use a payment management endpoint."
                )
            )

        check_supplier(cursor, purchase.supplier_id)

        cursor.execute(
            """
            SELECT id
            FROM purchases
            WHERE purchase_code = %s AND id != %s
            """,
            (purchase.purchase_code, purchase_id)
        )

        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail="Purchase code already exists."
            )

        cursor.execute(
            """
            SELECT
                product_id,
                quantity,
                purchase_price,
                discount_amount,
                tax_amount
            FROM purchase_items
            WHERE purchase_id = %s
            """,
            (purchase_id,)
        )

        old_items_rows = cursor.fetchall()

        old_items = [
            PurchaseItem(
                product_id=row["product_id"],
                quantity=row["quantity"],
                purchase_price=row["purchase_price"],
                discount_amount=row["discount_amount"],
                tax_amount=row["tax_amount"]
            )
            for row in old_items_rows
        ]

        lock_products(cursor, old_items + purchase.items)

        # Reverse the old purchase quantities.
        update_stock(cursor, old_items, -1)

        # Remove old purchase items.
        cursor.execute(
            "DELETE FROM purchase_items WHERE purchase_id = %s",
            (purchase_id,)
        )

        totals = calculate_purchase(
            purchase.items,
            purchase.extra_charges
        )

        total_amount = totals["total_amount"]
        paid_amount = old_paid_amount

        if paid_amount > total_amount:
            raise HTTPException(
                status_code=400,
                detail=(
                    "New purchase total cannot be less than "
                    "the amount already paid."
                )
            )

        due_amount = money(total_amount - paid_amount)
        payment_status = get_payment_status(
            total_amount,
            paid_amount
        )

        cursor.execute(
            """
            UPDATE purchases
            SET
                purchase_code = %s,
                supplier_id = %s,
                supplier_invoice_no = %s,
                purchase_date = %s,
                subtotal = %s,
                discount_amount = %s,
                tax_amount = %s,
                extra_charges = %s,
                total_amount = %s,
                paid_amount = %s,
                due_amount = %s,
                payment_status = %s,
                payment_method = %s,
                notes = %s
            WHERE id = %s
            """,
            (
                purchase.purchase_code,
                purchase.supplier_id,
                purchase.supplier_invoice_no,
                purchase.purchase_date,
                totals["subtotal"],
                totals["discount_amount"],
                totals["tax_amount"],
                totals["extra_charges"],
                total_amount,
                paid_amount,
                due_amount,
                payment_status,
                purchase.payment_method,
                purchase.notes,
                purchase_id
            )
        )

        save_purchase_items(
            cursor,
            purchase_id,
            purchase.items
        )

        # Add the updated purchase quantities.
        update_stock(cursor, purchase.items, 1)

        connection.commit()

        return {
            "success": True,
            "message": "Purchase updated and stock adjusted successfully",
            "purchase_id": purchase_id,
            "purchase_code": purchase.purchase_code,
            "total_amount": float(total_amount),
            "paid_amount": float(paid_amount),
            "due_amount": float(due_amount),
            "payment_status": payment_status
        }

    except HTTPException:
        if connection:
            connection.rollback()
        raise
    except mysql.connector.Error as error:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {error}"
        )
    except Exception as error:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# =========================
# CANCEL Purchase
# =========================

@router.patch("/{purchase_id}/cancel")
def cancel_purchase(purchase_id: int):
    connection = None
    cursor = None

    try:
        connection, cursor = get_connection_cursor()

        cursor.execute(
            """
            SELECT *
            FROM purchases
            WHERE id = %s
            FOR UPDATE
            """,
            (purchase_id,)
        )

        purchase = cursor.fetchone()

        if not purchase:
            raise HTTPException(
                status_code=404,
                detail="Purchase not found."
            )

        if purchase["status"] == "cancelled":
            raise HTTPException(
                status_code=400,
                detail="Purchase is already cancelled."
            )

        if money(purchase["paid_amount"]) > 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    "This purchase has payments. "
                    "Settle or reverse payments before cancelling."
                )
            )

        cursor.execute(
            """
            SELECT
                product_id,
                quantity,
                purchase_price,
                discount_amount,
                tax_amount
            FROM purchase_items
            WHERE purchase_id = %s
            """,
            (purchase_id,)
        )

        rows = cursor.fetchall()

        items = [
            PurchaseItem(
                product_id=row["product_id"],
                quantity=row["quantity"],
                purchase_price=row["purchase_price"],
                discount_amount=row["discount_amount"],
                tax_amount=row["tax_amount"]
            )
            for row in rows
        ]

        lock_products(cursor, items)

        # Remove quantities that were added by this purchase.
        update_stock(cursor, items, -1)

        cursor.execute(
            """
            UPDATE purchases
            SET status = 'cancelled'
            WHERE id = %s
            """,
            (purchase_id,)
        )

        connection.commit()

        return {
            "success": True,
            "message": "Purchase cancelled and stock reversed successfully",
            "purchase_id": purchase_id
        }

    except HTTPException:
        if connection:
            connection.rollback()
        raise
    except mysql.connector.Error as error:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {error}"
        )
    except Exception as error:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()