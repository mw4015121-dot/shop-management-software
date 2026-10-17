
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
from decimal import Decimal
from database import get_connection

router = APIRouter(
    prefix="/expenses",
    tags=["Expenses"]
)


class ExpenseCreate(BaseModel):
    expense_title: str = Field(min_length=1, max_length=150)
    category: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    expense_date: date
    payment_method: str = Field(default="Cash", max_length=50)
    notes: Optional[str] = None


class ExpenseUpdate(BaseModel):
    expense_title: str = Field(min_length=1, max_length=150)
    category: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    expense_date: date
    payment_method: str = Field(default="Cash", max_length=50)
    notes: Optional[str] = None


@router.get("/summary")
def expense_summary():
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                COUNT(*) AS total_records,
                COALESCE(SUM(amount), 0) AS total_expenses,
                COALESCE(
                    SUM(
                        CASE
                            WHEN expense_date = CURDATE()
                            THEN amount ELSE 0
                        END
                    ), 0
                ) AS today_expenses
            FROM expenses
        """)

        result = cursor.fetchone()

        return {
            "success": True,
            "total_records": int(result["total_records"]),
            "total_expenses": float(result["total_expenses"]),
            "today_expenses": float(result["today_expenses"])
        }

    finally:
        cursor.close()
        connection.close()


@router.get("/")
def get_expenses(
    search: str = "",
    category: str = "",
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100)
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="Start date cannot be after end date"
        )

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        conditions = []
        params = []

        if search.strip():
            term = f"%{search.strip()}%"
            conditions.append("""
                (
                    expense_title LIKE %s
                    OR category LIKE %s
                    OR payment_method LIKE %s
                    OR notes LIKE %s
                )
            """)
            params.extend([term, term, term, term])

        if category.strip():
            conditions.append("category = %s")
            params.append(category.strip())

        if start_date:
            conditions.append("expense_date >= %s")
            params.append(start_date)

        if end_date:
            conditions.append("expense_date <= %s")
            params.append(end_date)

        where_sql = (
            " WHERE " + " AND ".join(conditions)
            if conditions else ""
        )

        cursor.execute(
            f"SELECT COUNT(*) AS total FROM expenses {where_sql}",
            tuple(params)
        )
        total = int(cursor.fetchone()["total"])

        offset = (page - 1) * limit

        cursor.execute(
            f"""
            SELECT
                id, expense_title, category, amount,
                expense_date, payment_method, notes,
                created_at, updated_at
            FROM expenses
            {where_sql}
            ORDER BY expense_date DESC, id DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params) + (limit, offset)
        )

        records = cursor.fetchall()

        for item in records:
            item["amount"] = float(item["amount"])
            item["expense_date"] = str(item["expense_date"])
            item["created_at"] = str(item["created_at"])
            item["updated_at"] = str(item["updated_at"])

        return {
            "success": True,
            "expenses": records,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit
        }

    finally:
        cursor.close()
        connection.close()


@router.post("/")
def create_expense(expense: ExpenseCreate):
    title = expense.expense_title.strip()
    category = expense.category.strip()
    method = expense.payment_method.strip()

    if not title or not category or not method:
        raise HTTPException(
            status_code=400,
            detail="Title, category and payment method are required"
        )

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO expenses (
                expense_title, category, amount,
                expense_date, payment_method, notes
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                title,
                category,
                expense.amount,
                expense.expense_date,
                method,
                expense.notes
            )
        )

        connection.commit()
        new_id = cursor.lastrowid

        return {
            "success": True,
            "message": "Expense added successfully",
            "id": new_id
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


@router.put("/{expense_id}")
def update_expense(
    expense_id: int,
    expense: ExpenseUpdate
):
    title = expense.expense_title.strip()
    category = expense.category.strip()
    method = expense.payment_method.strip()

    if not title or not category or not method:
        raise HTTPException(
            status_code=400,
            detail="Title, category and payment method are required"
        )

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE expenses
            SET
                expense_title = %s,
                category = %s,
                amount = %s,
                expense_date = %s,
                payment_method = %s,
                notes = %s
            WHERE id = %s
            """,
            (
                title,
                category,
                expense.amount,
                expense.expense_date,
                method,
                expense.notes,
                expense_id
            )
        )

        if cursor.rowcount == 0:
            cursor.execute(
                "SELECT id FROM expenses WHERE id = %s",
                (expense_id,)
            )
            if not cursor.fetchone():
                raise HTTPException(
                    status_code=404,
                    detail="Expense not found"
                )

        connection.commit()

        return {
            "success": True,
            "message": "Expense updated successfully"
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


@router.delete("/{expense_id}")
def delete_expense(expense_id: int):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "DELETE FROM expenses WHERE id = %s",
            (expense_id,)
        )

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Expense not found"
            )

        connection.commit()

        return {
            "success": True,
            "message": "Expense deleted successfully"
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()
