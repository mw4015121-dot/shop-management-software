
from datetime import date, time
from decimal import Decimal
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from database import get_connection


router = APIRouter(
    prefix="/payments",
    tags=["Payments"]
)


# Payment create aur update model
class PaymentCreate(BaseModel):
    payment_type: Literal["Customer", "Supplier"]
    party_name: str = Field(min_length=1, max_length=150)
    reference: Optional[str] = Field(default=None, max_length=100)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    payment_method: str = Field(default="Cash", max_length=30)
    payment_date: date
    payment_time: Optional[time] = None
    status: Literal["Completed", "Pending"] = "Completed"
    notes: Optional[str] = Field(default=None, max_length=255)


def get_payment_or_404(cursor, payment_id):
    cursor.execute(
        "SELECT * FROM payments WHERE id = %s",
        (payment_id,)
    )

    payment = cursor.fetchone()

    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Payment record not found"
        )

    return payment


def clean_text(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


# 1. Payment summary
@router.get("/summary")
def payment_summary():
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                COUNT(*) AS total_records,

                COALESCE(
                    SUM(
                        CASE
                            WHEN payment_type = 'Customer'
                            AND status = 'Completed'
                            THEN amount ELSE 0
                        END
                    ), 0
                ) AS total_received,

                COALESCE(
                    SUM(
                        CASE
                            WHEN payment_type = 'Supplier'
                            AND status = 'Completed'
                            THEN amount ELSE 0
                        END
                    ), 0
                ) AS total_supplier_paid

            FROM payments
        """)

        row = cursor.fetchone()

        received = Decimal(str(row["total_received"]))
        supplier_paid = Decimal(str(row["total_supplier_paid"]))

        return {
            "success": True,
            "total_records": row["total_records"],
            "total_received": float(received),
            "total_supplier_paid": float(supplier_paid),
            "net_payments": float(received - supplier_paid)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# 2. List and search payments
@router.get("/")
def list_payments(
    search: Optional[str] = Query(default=None),
    payment_type: Optional[Literal["Customer", "Supplier"]] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500)
):
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        sql = "SELECT * FROM payments WHERE 1=1"
        params = []

        if search:
            term = f"%{search.strip()}%"

            sql += """
                AND (
                    party_name LIKE %s
                    OR reference LIKE %s
                    OR payment_method LIKE %s
                    OR notes LIKE %s
                )
            """

            params.extend([term, term, term, term])

        if payment_type:
            sql += " AND payment_type = %s"
            params.append(payment_type)

        if start_date:
            sql += " AND payment_date >= %s"
            params.append(start_date)

        if end_date:
            sql += " AND payment_date <= %s"
            params.append(end_date)

        sql += " ORDER BY id DESC LIMIT %s OFFSET %s"
        params.extend([limit, skip])

        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()

        for row in rows:
            row["amount"] = float(row["amount"])

            if row.get("payment_date"):
                row["payment_date"] = row["payment_date"].isoformat()

            if row.get("payment_time"):
                row["payment_time"] = str(row["payment_time"])

            if row.get("created_at"):
                row["created_at"] = row["created_at"].isoformat(
                    sep=" ", timespec="seconds"
                )

            if row.get("updated_at"):
                row["updated_at"] = row["updated_at"].isoformat(
                    sep=" ", timespec="seconds"
                )

        return rows

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# 3. Get one payment
@router.get("/{payment_id}")
def get_payment(payment_id: int):
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        payment = get_payment_or_404(cursor, payment_id)

        payment["amount"] = float(payment["amount"])

        if payment.get("payment_date"):
            payment["payment_date"] = payment["payment_date"].isoformat()

        if payment.get("payment_time"):
            payment["payment_time"] = str(payment["payment_time"])

        if payment.get("created_at"):
            payment["created_at"] = payment["created_at"].isoformat(
                sep=" ", timespec="seconds"
            )

        if payment.get("updated_at"):
            payment["updated_at"] = payment["updated_at"].isoformat(
                sep=" ", timespec="seconds"
            )

        return payment

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# 4. Create payment
@router.post("/")
def create_payment(payment: PaymentCreate):
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO payments (
                payment_type,
                party_name,
                reference,
                amount,
                payment_method,
                payment_date,
                payment_time,
                status,
                notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            payment.payment_type,
            payment.party_name.strip(),
            clean_text(payment.reference),
            payment.amount,
            payment.payment_method,
            payment.payment_date,
            payment.payment_time,
            payment.status,
            clean_text(payment.notes)
        ))

        payment_id = cursor.lastrowid
        conn.commit()

        return {
            "success": True,
            "message": "Payment saved successfully",
            "id": payment_id
        }

    except Exception as e:
        if conn:
            conn.rollback()

        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# 5. Update payment
@router.put("/{payment_id}")
def update_payment(payment_id: int, payment: PaymentCreate):
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        get_payment_or_404(cursor, payment_id)

        cursor.execute("""
            UPDATE payments
            SET
                payment_type = %s,
                party_name = %s,
                reference = %s,
                amount = %s,
                payment_method = %s,
                payment_date = %s,
                payment_time = %s,
                status = %s,
                notes = %s
            WHERE id = %s
        """, (
            payment.payment_type,
            payment.party_name.strip(),
            clean_text(payment.reference),
            payment.amount,
            payment.payment_method,
            payment.payment_date,
            payment.payment_time,
            payment.status,
            clean_text(payment.notes),
            payment_id
        ))

        conn.commit()

        return {
            "success": True,
            "message": "Payment updated successfully",
            "id": payment_id
        }

    except HTTPException:
        if conn:
            conn.rollback()
        raise

    except Exception as e:
        if conn:
            conn.rollback()

        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# 6. Delete payment
@router.delete("/{payment_id}")
def delete_payment(payment_id: int):
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        get_payment_or_404(cursor, payment_id)

        cursor.execute(
            "DELETE FROM payments WHERE id = %s",
            (payment_id,)
        )

        conn.commit()

        return {
            "success": True,
            "message": "Payment deleted successfully",
            "id": payment_id
        }

    except HTTPException:
        if conn:
            conn.rollback()
        raise

    except Exception as e:
        if conn:
            conn.rollback()

        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
