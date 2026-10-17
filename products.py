
from fastapi import APIRouter, UploadFile, File
import os
import uuid

from database import get_connection
from pydantic import BaseModel


router = APIRouter()


# =========================================================
# GET PRODUCTS
# Search + Pagination
# =========================================================

@router.get("/products")
def get_products(
    search: str = "",
    page: int = 1,
    limit: int = 20
):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    # -------------------------
    # Pagination validation
    # -------------------------

    if page < 1:
        page = 1

    if limit < 1:
        limit = 20

    if limit > 100:
        limit = 100

    offset = (page - 1) * limit

    search = search.strip()

    # =====================================================
    # SEARCH PRODUCTS
    # =====================================================

    if search:

        search_value = f"%{search}%"

        # -------------------------
        # Count search results
        # -------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM products
            WHERE
                product_name LIKE %s
                OR product_code LIKE %s
                OR barcode LIKE %s
                OR category LIKE %s
                OR brand LIKE %s
            """,
            (
                search_value,
                search_value,
                search_value,
                search_value,
                search_value
            )
        )

        total = cursor.fetchone()["total"]

        # -------------------------
        # Get search products
        # -------------------------

        cursor.execute(
            """
            SELECT *
            FROM products
            WHERE
                product_name LIKE %s
                OR product_code LIKE %s
                OR barcode LIKE %s
                OR category LIKE %s
                OR brand LIKE %s
            ORDER BY id DESC
            LIMIT %s OFFSET %s
            """,
            (
                search_value,
                search_value,
                search_value,
                search_value,
                search_value,
                limit,
                offset
            )
        )

    # =====================================================
    # GET ALL PRODUCTS
    # =====================================================

    else:

        # -------------------------
        # Count all products
        # -------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM products
            """
        )

        total = cursor.fetchone()["total"]

        # -------------------------
        # Get products
        # -------------------------

        cursor.execute(
            """
            SELECT *
            FROM products
            ORDER BY id DESC
            LIMIT %s OFFSET %s
            """,
            (
                limit,
                offset
            )
        )

    products = cursor.fetchall()

    cursor.close()
    connection.close()

    # =====================================================
    # RETURN RESULT
    # =====================================================

    return {
        "products": products,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit
    }


# =========================================================
# PRODUCT DATA MODEL
# =========================================================

class ProductCreate(BaseModel):

    product_name: str

    product_code: str | None = None

    barcode: str | None = None

    category: str | None = None

    brand: str | None = None

    purchase_price: float = 0

    original_price: float

    discount_type: str = "percentage"

    discount_value: float = 0

    stock_quantity: float = 0

    minimum_stock: float = 0

    unit: str = "Piece"

    description: str | None = None


# =========================================================
# ADD PRODUCT
# =========================================================

@router.post("/products")
def add_product(product: ProductCreate):

    connection = get_connection()
    cursor = connection.cursor()

    # =====================================================
    # CALCULATE DISCOUNT
    # =====================================================

    if product.discount_type == "percentage":

        discount_amount = (
            product.original_price
            * product.discount_value
            / 100
        )

    else:

        discount_amount = product.discount_value

    # =====================================================
    # CALCULATE FINAL PRICE
    # =====================================================

    final_price = (
        product.original_price
        - discount_amount
    )

    # Prevent negative price
    if final_price < 0:
        final_price = 0

    # =====================================================
    # INSERT PRODUCT
    # =====================================================

    query = """
        INSERT INTO products (
            product_name,
            product_code,
            barcode,
            category,
            brand,
            purchase_price,
            original_price,
            discount_type,
            discount_value,
            final_price,
            stock_quantity,
            minimum_stock,
            unit,
            description
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
    """

    values = (
        product.product_name,
        product.product_code,
        product.barcode,
        product.category,
        product.brand,
        product.purchase_price,
        product.original_price,
        product.discount_type,
        product.discount_value,
        final_price,
        product.stock_quantity,
        product.minimum_stock,
        product.unit,
        product.description
    )

    cursor.execute(
        query,
        values
    )

    connection.commit()

    product_id = cursor.lastrowid

    cursor.close()
    connection.close()

    return {
        "message": "Product Added Successfully",
        "product_id": product_id,
        "final_price": final_price
    }


# =========================================================
# UPDATE PRODUCT
# =========================================================

@router.put("/products/{product_id}")
def update_product(
    product_id: int,
    product: ProductCreate
):

    connection = get_connection()
    cursor = connection.cursor()

    # =====================================================
    # CALCULATE DISCOUNT
    # =====================================================

    if product.discount_type == "percentage":

        discount_amount = (
            product.original_price
            * product.discount_value
            / 100
        )

    else:

        discount_amount = product.discount_value

    # =====================================================
    # CALCULATE FINAL PRICE
    # =====================================================

    final_price = (
        product.original_price
        - discount_amount
    )

    # Prevent negative price
    if final_price < 0:
        final_price = 0

    # =====================================================
    # UPDATE PRODUCT
    # =====================================================

    query = """
        UPDATE products
        SET
            product_name = %s,
            product_code = %s,
            barcode = %s,
            category = %s,
            brand = %s,
            purchase_price = %s,
            original_price = %s,
            discount_type = %s,
            discount_value = %s,
            final_price = %s,
            stock_quantity = %s,
            minimum_stock = %s,
            unit = %s,
            description = %s
        WHERE id = %s
    """

    values = (
        product.product_name,
        product.product_code,
        product.barcode,
        product.category,
        product.brand,
        product.purchase_price,
        product.original_price,
        product.discount_type,
        product.discount_value,
        final_price,
        product.stock_quantity,
        product.minimum_stock,
        product.unit,
        product.description,
        product_id
    )

    cursor.execute(
        query,
        values
    )

    connection.commit()

    cursor.close()
    connection.close()

    return {
        "message": "Product Updated Successfully",
        "product_id": product_id,
        "final_price": final_price
    }


# =========================================================
# DELETE PRODUCT
# =========================================================

@router.delete("/products/{product_id}")
def delete_product(product_id: int):

    connection = get_connection()
    cursor = connection.cursor()

    query = """
        DELETE FROM products
        WHERE id = %s
    """

    cursor.execute(
        query,
        (product_id,)
    )

    connection.commit()

    cursor.close()
    connection.close()

    return {
        "message": "Product Deleted Successfully",
        "product_id": product_id
    }


# =========================================================
# UPLOAD PRODUCT IMAGE
# =========================================================

@router.post("/products/{product_id}/image")
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...)
):

    # =====================================================
    # ALLOWED IMAGE TYPES
    # =====================================================

    allowed_extensions = [
        ".jpg",
        ".jpeg",
        ".png",
        ".webp"
    ]

    # =====================================================
    # CHECK FILE NAME
    # =====================================================

    if not file.filename:

        return {
            "message": "Please select an image"
        }

    # =====================================================
    # GET FILE EXTENSION
    # =====================================================

    original_extension = os.path.splitext(
        file.filename
    )[1].lower()

    # =====================================================
    # CHECK EXTENSION
    # =====================================================

    if original_extension not in allowed_extensions:

        return {
            "message": (
                "Only JPG, JPEG, PNG and WEBP "
                "images are allowed"
            )
        }

    # =====================================================
    # CHECK PRODUCT EXISTS
    # =====================================================

    connection = get_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute(
        """
        SELECT id, product_image
        FROM products
        WHERE id = %s
        """,
        (product_id,)
    )

    product = cursor.fetchone()

    cursor.close()
    connection.close()

    if not product:

        return {
            "message": "Product not found"
        }

    # =====================================================
    # CREATE UNIQUE FILE NAME
    # =====================================================

    new_filename = (
        f"{uuid.uuid4().hex}"
        f"{original_extension}"
    )

    # =====================================================
    # UPLOAD FOLDER
    # =====================================================

    upload_folder = "uploads"

    os.makedirs(
        upload_folder,
        exist_ok=True
    )

    # =====================================================
    # FULL FILE PATH
    # =====================================================

    file_path = os.path.join(
        upload_folder,
        new_filename
    )

    # =====================================================
    # SAVE IMAGE
    # =====================================================

    with open(
        file_path,
        "wb"
    ) as image_file:

        while content := await file.read(
            1024 * 1024
        ):

            image_file.write(
                content
            )

    await file.close()

    # =====================================================
    # DELETE OLD IMAGE
    # =====================================================

    old_image = product.get(
        "product_image"
    )

    if old_image:

        old_file_path = os.path.join(
            upload_folder,
            old_image
        )

        if os.path.exists(
            old_file_path
        ):

            try:

                os.remove(
                    old_file_path
                )

            except OSError:

                pass

    # =====================================================
    # SAVE NEW IMAGE IN DATABASE
    # =====================================================

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE products
        SET product_image = %s
        WHERE id = %s
        """,
        (
            new_filename,
            product_id
        )
    )

    connection.commit()

    cursor.close()
    connection.close()

    # =====================================================
    # RESPONSE
    # =====================================================

    return {
        "message": "Product Image Uploaded Successfully",
        "product_id": product_id,
        "filename": new_filename,
        "image_url": f"/uploads/{new_filename}"
    }
