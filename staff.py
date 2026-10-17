
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import date
from decimal import Decimal
from database import get_connection

router = APIRouter(prefix="/staff", tags=["Staff Management"])


# ==================== REQUEST MODELS ====================

class StaffCreate(BaseModel):
    staff_code: str = Field(min_length=1, max_length=30)
    staff_name: str = Field(min_length=1, max_length=150)
    designation: str = Field(min_length=1, max_length=100)
    joining_date: date
    basic_salary: Decimal = Field(ge=0)
    status: Literal["Active", "Inactive"] = "Active"


class AttendanceCreate(BaseModel):
    staff_id: int = Field(gt=0)
    attendance_date: date
    attendance_status: Literal[
        "Present", "Absent", "Late", "Leave"
    ] = "Present"
    notes: Optional[str] = None


class SalaryCreate(BaseModel):
    staff_id: int = Field(gt=0)
    salary_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    basic_salary: Decimal = Field(ge=0)
    bonus: Decimal = Field(default=Decimal("0"), ge=0)
    deductions: Decimal = Field(default=Decimal("0"), ge=0)
    paid_amount: Decimal = Field(default=Decimal("0"), ge=0)
    payment_date: Optional[date] = None
    notes: Optional[str] = None


# ==================== STAFF SUMMARY ====================

@router.get("/summary")
def staff_summary():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                COUNT(*) AS total_staff,
                COALESCE(SUM(status = 'Active'), 0) AS active_staff,
                COALESCE(SUM(status = 'Inactive'), 0) AS inactive_staff
            FROM staff
        """)
        return {"success": True, **cursor.fetchone()}
    finally:
        cursor.close()
        conn.close()


# ==================== GET ALL STAFF ====================

@router.get("/")
def get_staff(
    search: str = "",
    status: str = "",
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100)
):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        conditions = []
        params = []

        if search.strip():
            conditions.append(
                "(staff_name LIKE %s OR staff_code LIKE %s OR designation LIKE %s)"
            )
            term = f"%{search.strip()}%"
            params.extend([term, term, term])

        if status in ("Active", "Inactive"):
            conditions.append("status = %s")
            params.append(status)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""

        cursor.execute(
            f"SELECT COUNT(*) AS total FROM staff{where}", params
        )
        total = cursor.fetchone()["total"]

        cursor.execute(
            f"""
            SELECT * FROM staff{where}
            ORDER BY id DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, (page - 1) * limit]
        )

        return {
            "success": True,
            "staff": cursor.fetchall(),
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit
        }
    finally:
        cursor.close()
        conn.close()


# ==================== GET STAFF BY ID ====================

@router.get("/{staff_id}")
def get_staff_by_id(staff_id: int):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT * FROM staff WHERE id = %s",
            (staff_id,)
        )
        staff = cursor.fetchone()

        if not staff:
            raise HTTPException(
                status_code=404,
                detail="Staff not found"
            )

        return {"success": True, "staff": staff}
    finally:
        cursor.close()
        conn.close()


# ==================== ADD STAFF ====================

@router.post("/")
def create_staff(data: StaffCreate):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            INSERT INTO staff
            (staff_code, staff_name, designation, joining_date,
             basic_salary, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                data.staff_code.strip(),
                data.staff_name.strip(),
                data.designation.strip(),
                data.joining_date,
                data.basic_salary,
                data.status
            )
        )

        conn.commit()
        staff_id = cursor.lastrowid

        cursor.execute(
            "SELECT * FROM staff WHERE id = %s",
            (staff_id,)
        )

        return {
            "success": True,
            "message": "Staff added successfully",
            "staff": cursor.fetchone()
        }

    except Exception as exc:
        conn.rollback()

        if getattr(exc, "errno", None) == 1062:
            raise HTTPException(
                status_code=409,
                detail="Staff code already exists"
            )

        raise HTTPException(
            status_code=500,
            detail="Could not add staff"
        )
    finally:
        cursor.close()
        conn.close()


# ==================== UPDATE STAFF ====================

@router.put("/{staff_id}")
def update_staff(staff_id: int, data: StaffCreate):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            UPDATE staff
            SET staff_code = %s,
                staff_name = %s,
                designation = %s,
                joining_date = %s,
                basic_salary = %s,
                status = %s
            WHERE id = %s
            """,
            (
                data.staff_code.strip(),
                data.staff_name.strip(),
                data.designation.strip(),
                data.joining_date,
                data.basic_salary,
                data.status,
                staff_id
            )
        )

        cursor.execute(
            "SELECT * FROM staff WHERE id = %s",
            (staff_id,)
        )
        staff = cursor.fetchone()

        if not staff:
            conn.rollback()
            raise HTTPException(
                status_code=404,
                detail="Staff not found"
            )

        conn.commit()

        return {
            "success": True,
            "message": "Staff updated successfully",
            "staff": staff
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()

        if getattr(exc, "errno", None) == 1062:
            raise HTTPException(
                status_code=409,
                detail="Staff code already exists"
            )

        raise HTTPException(
            status_code=500,
            detail="Could not update staff"
        )
    finally:
        cursor.close()
        conn.close()


# ==================== DELETE STAFF ====================

@router.delete("/{staff_id}")
def delete_staff(staff_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "DELETE FROM staff WHERE id = %s",
            (staff_id,)
        )

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Staff not found"
            )

        conn.commit()

        return {
            "success": True,
            "message": "Staff deleted successfully"
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()

        raise HTTPException(
            status_code=409,
            detail=(
                "Staff has attendance or salary records. "
                "Change status to Inactive instead."
            )
        )
    finally:
        cursor.close()
        conn.close()


# ==================== ATTENDANCE LIST ====================

@router.get("/attendance/list")
def get_attendance(
    staff_id: Optional[int] = None,
    attendance_date: Optional[date] = None
):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        query = """
            SELECT a.*, s.staff_code, s.staff_name
            FROM staff_attendance a
            JOIN staff s ON s.id = a.staff_id
            WHERE 1=1
        """
        params = []

        if staff_id is not None:
            query += " AND a.staff_id = %s"
            params.append(staff_id)

        if attendance_date is not None:
            query += " AND a.attendance_date = %s"
            params.append(attendance_date)

        query += " ORDER BY a.attendance_date DESC, a.id DESC"

        cursor.execute(query, params)

        return {
            "success": True,
            "attendance": cursor.fetchall()
        }
    finally:
        cursor.close()
        conn.close()


# ==================== MARK ATTENDANCE ====================

@router.post("/attendance")
def mark_attendance(data: AttendanceCreate):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT id FROM staff WHERE id = %s",
            (data.staff_id,)
        )

        if not cursor.fetchone():
            raise HTTPException(
                status_code=404,
                detail="Staff not found"
            )

        cursor.execute(
            """
            INSERT INTO staff_attendance
            (staff_id, attendance_date, attendance_status, notes)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                attendance_status = VALUES(attendance_status),
                notes = VALUES(notes)
            """,
            (
                data.staff_id,
                data.attendance_date,
                data.attendance_status,
                data.notes
            )
        )

        conn.commit()

        return {
            "success": True,
            "message": "Attendance saved successfully"
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not save attendance"
        )
    finally:
        cursor.close()
        conn.close()


# ==================== SALARY LIST ====================

@router.get("/salary/list")
def get_salaries(
    staff_id: Optional[int] = None,
    salary_month: Optional[str] = None
):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        query = """
            SELECT
                sl.*,
                s.staff_code,
                s.staff_name,
                (sl.basic_salary + sl.bonus - sl.deductions)
                    AS net_salary,
                (sl.basic_salary + sl.bonus - sl.deductions
                    - sl.paid_amount) AS remaining_salary
            FROM staff_salaries sl
            JOIN staff s ON s.id = sl.staff_id
            WHERE 1=1
        """
        params = []

        if staff_id is not None:
            query += " AND sl.staff_id = %s"
            params.append(staff_id)

        if salary_month:
            query += " AND sl.salary_month = %s"
            params.append(salary_month)

        query += " ORDER BY sl.salary_month DESC, sl.id DESC"

        cursor.execute(query, params)

        return {
            "success": True,
            "salaries": cursor.fetchall()
        }
    finally:
        cursor.close()
        conn.close()


# ==================== SAVE SALARY ====================

@router.post("/salary")
def save_salary(data: SalaryCreate):
    net_salary = (
        data.basic_salary + data.bonus - data.deductions
    )

    if net_salary < 0:
        raise HTTPException(
            status_code=400,
            detail="Deductions cannot exceed basic salary plus bonus"
        )

    if data.paid_amount > net_salary:
        raise HTTPException(
            status_code=400,
            detail="Paid amount cannot exceed net salary"
        )

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT id FROM staff WHERE id = %s",
            (data.staff_id,)
        )

        if not cursor.fetchone():
            raise HTTPException(
                status_code=404,
                detail="Staff not found"
            )

        cursor.execute(
            """
            INSERT INTO staff_salaries
            (staff_id, salary_month, basic_salary, bonus,
             deductions, paid_amount, payment_date, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                basic_salary = VALUES(basic_salary),
                bonus = VALUES(bonus),
                deductions = VALUES(deductions),
                paid_amount = VALUES(paid_amount),
                payment_date = VALUES(payment_date),
                notes = VALUES(notes)
            """,
            (
                data.staff_id,
                data.salary_month,
                data.basic_salary,
                data.bonus,
                data.deductions,
                data.paid_amount,
                data.payment_date,
                data.notes
            )
        )

        conn.commit()

        return {
            "success": True,
            "message": "Salary saved successfully"
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not save salary"
        )
    finally:
        cursor.close()
        conn.close()
