
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from database import get_connection

router = APIRouter(
    prefix="/suppliers",
    tags=["Suppliers"]
)


# =========================
# Supplier Data Model
# =========================

class SupplierCreate(BaseModel):
    supplier_code: str
    supplier_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    company_name: Optional[str] = None
    address: Optional[str] = None
    opening_balance: float = 0.0
    status: str = "active"


class SupplierUpdate(BaseModel):
    supplier_code: str
    supplier_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    company_name: Optional[str] = None
    address: Optional[str] = None
    opening_balance: float = 0.0
    status: str = "active"


# =========================
# Get All Suppliers
# =========================

@router.get("/")
def get_suppliers(search: Optional[str] = None):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        if search:
            keyword = f"%{search}%"
            cursor.execute(
                """
                SELECT * FROM suppliers
                WHERE supplier_code LIKE %s
                   OR supplier_name LIKE %s
                   OR company_name LIKE %s
                   OR phone LIKE %s
                ORDER BY id DESC
                """,
                (keyword, keyword, keyword, keyword)
            )
        else:
            cursor.execute(
                "SELECT * FROM suppliers ORDER BY id DESC"
            )

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


# =========================
# Get One Supplier
# =========================

@router.get("/{supplier_id}")
def get_supplier(supplier_id: int):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT * FROM suppliers WHERE id = %s",
            (supplier_id,)
        )
        supplier = cursor.fetchone()

        if not supplier:
            raise HTTPException(
                status_code=404,
                detail="Supplier not found"
            )

        return supplier

    finally:
        cursor.close()
        connection.close()


# =========================
# Add Supplier
# =========================

@router.post("/")
def add_supplier(supplier: SupplierCreate):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO suppliers (
                supplier_code,
                supplier_name,
                phone,
                email,
                company_name,
                address,
                opening_balance,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                supplier.supplier_code,
                supplier.supplier_name,
                supplier.phone,
                supplier.email,
                supplier.company_name,
                supplier.address,
                supplier.opening_balance,
                supplier.status
            )
        )

        connection.commit()

        return {
            "success": True,
            "message": "Supplier added successfully",
            "supplier_id": cursor.lastrowid
        }

    except Exception as error:
        connection.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    finally:
        cursor.close()
        connection.close()


# =========================
# Update Supplier
# =========================

@router.put("/{supplier_id}")
def update_supplier(
    supplier_id: int,
    supplier: SupplierUpdate
):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "SELECT id FROM suppliers WHERE id = %s",
            (supplier_id,)
        )

        if not cursor.fetchone():
            raise HTTPException(
                status_code=404,
                detail="Supplier not found"
            )

        cursor.execute(
            """
            UPDATE suppliers
            SET supplier_code = %s,
                supplier_name = %s,
                phone = %s,
                email = %s,
                company_name = %s,
                address = %s,
                opening_balance = %s,
                status = %s
            WHERE id = %s
            """,
            (
                supplier.supplier_code,
                supplier.supplier_name,
                supplier.phone,
                supplier.email,
                supplier.company_name,
                supplier.address,
                supplier.opening_balance,
                supplier.status,
                supplier_id
            )
        )

        connection.commit()

        return {
            "success": True,
            "message": "Supplier updated successfully"
        }

    except HTTPException:
        raise

    except Exception as error:
        connection.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    finally:
        cursor.close()
        connection.close()


# =========================
# Delete Supplier
# =========================

@router.delete("/{supplier_id}")
def delete_supplier(supplier_id: int):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "DELETE FROM suppliers WHERE id = %s",
            (supplier_id,)
        )

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Supplier not found"
            )

        connection.commit()

        return {
            "success": True,
            "message": "Supplier deleted successfully"
        }

    except HTTPException:
        raise

    except Exception as error:
        connection.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    finally:
        cursor.close()
        connection.close()
