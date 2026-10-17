from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_connection


router = APIRouter(prefix="/customers", tags=["Customers"])


class CustomerCreate(BaseModel):
    customer_code: str | None = None
    customer_name: str
    total_purchase: float = 0
    total_paid: float = 0
    total_due: float = 0
    status: str = "active"


# Get all customers + Search
@router.get("")
def get_customers(search: str = ""):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    if search:
        sql = """
            SELECT *
            FROM customers
            WHERE customer_name LIKE %s
               OR customer_code LIKE %s
            ORDER BY id DESC
        """
        value = f"%{search}%"
        cursor.execute(sql, (value, value))
    else:
        cursor.execute("""
            SELECT *
            FROM customers
            ORDER BY id DESC
        """)

    customers = cursor.fetchall()

    cursor.close()
    connection.close()

    return customers


# Add Customer
@router.post("")
def add_customer(customer: CustomerCreate):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        sql = """
            INSERT INTO customers
            (
                customer_code,
                customer_name,
                total_purchase,
                total_paid,
                total_due,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        cursor.execute(
            sql,
            (
                customer.customer_code,
                customer.customer_name,
                customer.total_purchase,
                customer.total_paid,
                customer.total_due,
                customer.status
            )
        )

        connection.commit()

        customer_id = cursor.lastrowid

        cursor.execute(
            "SELECT * FROM customers WHERE id = %s",
            (customer_id,)
        )

        new_customer = cursor.fetchone()

        return new_customer

    except Exception as e:
        connection.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    finally:
        cursor.close()
        connection.close()


# Edit Customer
@router.put("/{customer_id}")
def update_customer(customer_id: int, customer: CustomerCreate):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        sql = """
            UPDATE customers
            SET
                customer_code = %s,
                customer_name = %s,
                total_purchase = %s,
                total_paid = %s,
                total_due = %s,
                status = %s
            WHERE id = %s
        """

        cursor.execute(
            sql,
            (
                customer.customer_code,
                customer.customer_name,
                customer.total_purchase,
                customer.total_paid,
                customer.total_due,
                customer.status,
                customer_id
            )
        )

        connection.commit()

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Customer not found"
            )

        cursor.execute(
            "SELECT * FROM customers WHERE id = %s",
            (customer_id,)
        )

        updated_customer = cursor.fetchone()

        return updated_customer

    except HTTPException:
        raise

    except Exception as e:
        connection.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    finally:
        cursor.close()
        connection.close()


# Delete Customer
@router.delete("/{customer_id}")
def delete_customer(customer_id: int):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "DELETE FROM customers WHERE id = %s",
            (customer_id,)
        )

        connection.commit()

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Customer not found"
            )

        return {
            "message": "Customer deleted successfully"
        }

    except HTTPException:
        raise

    except Exception as e:
        connection.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    finally:
        cursor.close()
        connection.close()