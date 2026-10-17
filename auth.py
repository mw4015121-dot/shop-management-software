
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from database import get_connection

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(data: LoginRequest, request: Request):

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT id, username, password_hash
            FROM admin
            WHERE username = %s
            """,
            (data.username,)
        )

        admin = cursor.fetchone()

        if not admin or data.password != admin["password_hash"]:
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password"
            )

        # Create a server-signed session cookie
        request.session.clear()
        request.session["admin_id"] = admin["id"]
        request.session["username"] = admin["username"]

        return {
            "message": "Login successful",
            "admin_id": admin["id"],
            "username": admin["username"]
        }

    finally:
        cursor.close()
        connection.close()


@router.get("/me")
def current_admin(request: Request):

    admin_id = request.session.get("admin_id")
    username = request.session.get("username")

    if not admin_id or not username:
        raise HTTPException(
            status_code=401,
            detail="Please login first"
        )

    return {
        "logged_in": True,
        "admin_id": admin_id,
        "username": username
    }


@router.post("/logout")
def logout(request: Request):

    request.session.clear()

    return {
        "message": "Logout successful"
    }
