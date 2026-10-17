
from fastapi import APIRouter, HTTPException, Query
from database import get_connection

router = APIRouter(
    prefix="/inventory",
    tags=["Inventory"]
)


# ==========================================
# INVENTORY SUMMARY
# ==========================================

@router.get("/summary")
def inventory_summary():
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                COUNT(*) AS total_products,
                COALESCE(SUM(stock_quantity), 0) AS total_stock,
                COALESCE(SUM(
                    CASE
                        WHEN stock_quantity <= 0 THEN 1
                        ELSE 0
                    END
                ), 0) AS out_of_stock,
                COALESCE(SUM(
                    CASE
                        WHEN stock_quantity > 0
                         AND minimum_stock > 0
                         AND stock_quantity <= minimum_stock
                        THEN 1
                        ELSE 0
                    END
                ), 0) AS low_stock
            FROM products
        """)

        result = cursor.fetchone()

        return {
            "success": True,
            "total_products": int(result["total_products"]),
            "total_stock": float(result["total_stock"]),
            "low_stock": int(result["low_stock"]),
            "out_of_stock": int(result["out_of_stock"])
        }

    finally:
        cursor.close()
        connection.close()


# ==========================================
# INVENTORY PRODUCT LIST
# Search, Filter and Pagination
# ==========================================

@router.get("/")
def get_inventory(
    search: str = "",
    status: str = Query(
        default="all",
        pattern="^(all|low|out|available)$"
    ),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100)
):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        conditions = []
        params = []

        search = search.strip()

        if search:
            search_value = f"%{search}%"

            conditions.append("""
                (
                    product_name LIKE %s
                    OR product_code LIKE %s
                    OR barcode LIKE %s
                    OR category LIKE %s
                    OR brand LIKE %s
                )
            """)

            params.extend([search_value] * 5)

        if status == "low":
            conditions.append("""
                stock_quantity > 0
                AND minimum_stock > 0
                AND stock_quantity <= minimum_stock
            """)

        elif status == "out":
            conditions.append("stock_quantity <= 0")

        elif status == "available":
            conditions.append("stock_quantity > 0")

        where_clause = (
            " WHERE " + " AND ".join(conditions)
            if conditions else ""
        )

        cursor.execute(
            f"""
            SELECT COUNT(*) AS total
            FROM products
            {where_clause}
            """,
            tuple(params)
        )

        total = int(cursor.fetchone()["total"])
        offset = (page - 1) * limit

        cursor.execute(
            f"""
            SELECT
                id,
                product_name,
                product_code,
                barcode,
                category,
                brand,
                stock_quantity,
                minimum_stock,
                unit
            FROM products
            {where_clause}
            ORDER BY id DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params) + (limit, offset)
        )

        products = cursor.fetchall()

        for product in products:
            stock = float(product["stock_quantity"] or 0)
            minimum = float(product["minimum_stock"] or 0)

            product["stock_quantity"] = stock
            product["minimum_stock"] = minimum

            if stock <= 0:
                product["stock_status"] = "Out of Stock"
            elif minimum > 0 and stock <= minimum:
                product["stock_status"] = "Low Stock"
            else:
                product["stock_status"] = "In Stock"

        return {
            "success": True,
            "products": products,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit
        }

    finally:
        cursor.close()
        connection.close()


# ==========================================
# SINGLE PRODUCT STOCK DETAILS
# ==========================================

@router.get("/{product_id}")
def get_product_inventory(product_id: int):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                id,
                product_name,
                product_code,
                barcode,
                stock_quantity,
                minimum_stock,
                unit
            FROM products
            WHERE id = %s
        """, (product_id,))

        product = cursor.fetchone()

        if not product:
            raise HTTPException(
                status_code=404,
                detail="Product not found"
            )

        stock = float(product["stock_quantity"] or 0)
        minimum = float(product["minimum_stock"] or 0)

        product["stock_quantity"] = stock
        product["minimum_stock"] = minimum

        if stock <= 0:
            product["stock_status"] = "Out of Stock"
        elif minimum > 0 and stock <= minimum:
            product["stock_status"] = "Low Stock"
        else:
            product["stock_status"] = "In Stock"

        return {
            "success": True,
            "product": product
        }

    finally:
        cursor.close()
        connection.close()
