import os
import time
import urllib.parse
import mysql.connector

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass



def get_db_config():
    """Extract MySQL database configuration from environment variables.

    Supports:
    - MYSQL_URL or DATABASE_URL (Railway MySQL connection string)
    - Railway individual variables (MYSQLHOST, MYSQLPORT, MYSQLUSER, MYSQLPASSWORD, MYSQLDATABASE)
    - Custom variables (DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME)
    - Local fallback defaults (localhost, 3306, root, 1234, shop_management)
    """
    db_url = os.getenv("MYSQL_URL") or os.getenv("DATABASE_URL")
    if db_url and (db_url.startswith("mysql://") or db_url.startswith("mysql+pymysql://")):
        # If schema is mysql+pymysql, normalize to mysql
        if db_url.startswith("mysql+pymysql://"):
            db_url = "mysql://" + db_url[len("mysql+pymysql://"):]

        parsed = urllib.parse.urlparse(db_url)
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 3306,
            "user": urllib.parse.unquote(parsed.username) if parsed.username else "root",
            "password": urllib.parse.unquote(parsed.password) if parsed.password else "",
            "database": urllib.parse.unquote(parsed.path.lstrip("/")) if parsed.path else "shop_management"
        }

    host = os.getenv("DB_HOST") or os.getenv("MYSQLHOST") or "localhost"
    user = os.getenv("DB_USER") or os.getenv("MYSQLUSER") or "root"
    password = os.getenv("DB_PASSWORD") or os.getenv("MYSQLPASSWORD") or "1234"
    database = os.getenv("DB_NAME") or os.getenv("MYSQLDATABASE") or "shop_management"

    port_str = os.getenv("DB_PORT") or os.getenv("MYSQLPORT") or "3306"
    try:
        port = int(port_str)
    except (ValueError, TypeError):
        port = 3306

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database
    }


def get_connection():
    """Create and return a MySQL connection.

    If database does not exist (error 1049), attempts to create it automatically.
    """
    config = get_db_config()
    try:
        return mysql.connector.connect(**config)
    except mysql.connector.Error as err:
        # 1049: ER_BAD_DB_ERROR (Unknown database)
        if getattr(err, "errno", None) == 1049:
            db_name = config.get("database")
            temp_config = config.copy()
            temp_config.pop("database", None)
            temp_conn = mysql.connector.connect(**temp_config)
            cursor = temp_conn.cursor()
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            temp_conn.commit()
            cursor.close()
            temp_conn.close()
            return mysql.connector.connect(**config)
        raise


TABLE_DEFINITIONS = [
    """
    CREATE TABLE IF NOT EXISTS `admin` (
        `id` INT NOT NULL AUTO_INCREMENT,
        `username` VARCHAR(50) NOT NULL,
        `password_hash` VARCHAR(255) NOT NULL,
        `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        UNIQUE KEY `username` (`username`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS `customers` (
        `id` INT NOT NULL AUTO_INCREMENT,
        `customer_code` VARCHAR(50) DEFAULT NULL,
        `customer_name` VARCHAR(150) NOT NULL,
        `total_purchase` DECIMAL(12,2) DEFAULT '0.00',
        `total_paid` DECIMAL(12,2) DEFAULT '0.00',
        `total_due` DECIMAL(12,2) DEFAULT '0.00',
        `status` ENUM('active','inactive') DEFAULT 'active',
        `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
        `updated_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        UNIQUE KEY `customer_code` (`customer_code`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS `suppliers` (
        `id` INT NOT NULL AUTO_INCREMENT,
        `supplier_code` VARCHAR(50) NOT NULL,
        `supplier_name` VARCHAR(150) NOT NULL,
        `phone` VARCHAR(30) DEFAULT NULL,
        `email` VARCHAR(150) DEFAULT NULL,
        `company_name` VARCHAR(150) DEFAULT NULL,
        `address` TEXT,
        `opening_balance` DECIMAL(12,2) NOT NULL DEFAULT '0.00',
        `status` ENUM('active','inactive') NOT NULL DEFAULT 'active',
        `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
        `updated_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        UNIQUE KEY `supplier_code` (`supplier_code`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS `products` (
        `id` INT NOT NULL AUTO_INCREMENT,
        `product_name` VARCHAR(150) NOT NULL,
        `product_image` VARCHAR(255) DEFAULT NULL,
        `product_code` VARCHAR(100) DEFAULT NULL,
        `barcode` VARCHAR(100) DEFAULT NULL,
        `category` VARCHAR(100) DEFAULT NULL,
        `brand` VARCHAR(100) DEFAULT NULL,
        `purchase_price` DECIMAL(10,2) DEFAULT '0.00',
        `original_price` DECIMAL(10,2) NOT NULL,
        `discount_type` ENUM('percentage','fixed') DEFAULT 'percentage',
        `discount_value` DECIMAL(10,2) DEFAULT '0.00',
        `final_price` DECIMAL(10,2) NOT NULL,
        `stock_quantity` DECIMAL(10,2) DEFAULT '0.00',
        `minimum_stock` DECIMAL(10,2) DEFAULT '0.00',
        `unit` VARCHAR(50) DEFAULT 'Piece',
        `description` TEXT,
        `status` ENUM('active','inactive') DEFAULT 'active',
        `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
        `updated_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        UNIQUE KEY `product_code` (`product_code`),
        UNIQUE KEY `barcode` (`barcode`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS `purchases` (
        `id` INT NOT NULL AUTO_INCREMENT,
        `purchase_code` VARCHAR(50) NOT NULL,
        `supplier_id` INT NOT NULL,
        `supplier_invoice_no` VARCHAR(100) DEFAULT NULL,
        `purchase_date` DATE NOT NULL,
        `subtotal` DECIMAL(12,2) NOT NULL DEFAULT '0.00',
        `discount_amount` DECIMAL(12,2) NOT NULL DEFAULT '0.00',
        `tax_amount` DECIMAL(12,2) NOT NULL DEFAULT '0.00',
        `extra_charges` DECIMAL(12,2) NOT NULL DEFAULT '0.00',
        `total_amount` DECIMAL(12,2) NOT NULL DEFAULT '0.00',
        `paid_amount` DECIMAL(12,2) NOT NULL DEFAULT '0.00',
        `due_amount` DECIMAL(12,2) NOT NULL DEFAULT '0.00',
        `payment_status` ENUM('unpaid','partial','paid') NOT NULL DEFAULT 'unpaid',
        `payment_method` VARCHAR(50) DEFAULT NULL,
        `notes` TEXT,
        `status` ENUM('pending','completed','cancelled') NOT NULL DEFAULT 'completed',
        `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
        `updated_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        UNIQUE KEY `purchase_code` (`purchase_code`),
        KEY `fk_purchases_supplier` (`supplier_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS `purchase_items` (
        `id` INT NOT NULL AUTO_INCREMENT,
        `purchase_id` INT NOT NULL,
        `product_id` INT NOT NULL,
        `quantity` DECIMAL(12,3) NOT NULL DEFAULT '1.000',
        `purchase_price` DECIMAL(12,2) NOT NULL DEFAULT '0.00',
        `discount_amount` DECIMAL(12,2) NOT NULL DEFAULT '0.00',
        `tax_amount` DECIMAL(12,2) NOT NULL DEFAULT '0.00',
        `total_amount` DECIMAL(12,2) NOT NULL DEFAULT '0.00',
        `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        KEY `fk_purchase_items_purchase` (`purchase_id`),
        KEY `fk_purchase_items_product` (`product_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS `sales` (
        `id` INT NOT NULL AUTO_INCREMENT,
        `invoice_no` VARCHAR(50) NOT NULL,
        `customer_id` INT DEFAULT NULL,
        `sale_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        `subtotal` DECIMAL(12,2) NOT NULL DEFAULT '0.00',
        `discount` DECIMAL(12,2) NOT NULL DEFAULT '0.00',
        `grand_total` DECIMAL(12,2) NOT NULL DEFAULT '0.00',
        `paid_amount` DECIMAL(12,2) NOT NULL DEFAULT '0.00',
        `due_amount` DECIMAL(12,2) NOT NULL DEFAULT '0.00',
        `payment_method` VARCHAR(30) NOT NULL DEFAULT 'Cash',
        `notes` TEXT,
        `status` VARCHAR(20) NOT NULL DEFAULT 'Completed',
        PRIMARY KEY (`id`),
        UNIQUE KEY `invoice_no` (`invoice_no`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS `sale_items` (
        `id` INT NOT NULL AUTO_INCREMENT,
        `sale_id` INT NOT NULL,
        `product_id` INT NOT NULL,
        `product_name` VARCHAR(255) NOT NULL,
        `quantity` DECIMAL(12,3) NOT NULL,
        `unit_price` DECIMAL(12,2) NOT NULL,
        `line_total` DECIMAL(12,2) NOT NULL,
        PRIMARY KEY (`id`),
        KEY `idx_sale_id` (`sale_id`),
        KEY `idx_product_id` (`product_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS `sales_returns` (
        `id` INT NOT NULL AUTO_INCREMENT,
        `return_no` VARCHAR(60) NOT NULL,
        `sale_id` INT NOT NULL,
        `customer_id` INT DEFAULT NULL,
        `refund_method` VARCHAR(30) NOT NULL,
        `return_total` DECIMAL(12,2) NOT NULL DEFAULT '0.00',
        `notes` TEXT,
        `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        UNIQUE KEY `return_no` (`return_no`),
        KEY `idx_return_sale` (`sale_id`),
        KEY `idx_return_customer` (`customer_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS `sales_return_items` (
        `id` INT NOT NULL AUTO_INCREMENT,
        `return_id` INT NOT NULL,
        `sale_item_id` INT NOT NULL,
        `product_id` INT NOT NULL,
        `product_name` VARCHAR(255) NOT NULL,
        `quantity` DECIMAL(12,3) NOT NULL,
        `unit_price` DECIMAL(12,2) NOT NULL,
        `line_total` DECIMAL(12,2) NOT NULL,
        PRIMARY KEY (`id`),
        KEY `idx_return_item` (`return_id`),
        KEY `idx_original_sale_item` (`sale_item_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS `customer_credit_transactions` (
        `id` INT NOT NULL AUTO_INCREMENT,
        `customer_id` INT NOT NULL,
        `return_id` INT NOT NULL,
        `amount` DECIMAL(12,2) NOT NULL,
        `transaction_type` VARCHAR(30) NOT NULL DEFAULT 'Return Credit',
        `description` VARCHAR(255) DEFAULT NULL,
        `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        UNIQUE KEY `uq_credit_return` (`return_id`),
        KEY `idx_credit_customer` (`customer_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS `expenses` (
        `id` INT NOT NULL AUTO_INCREMENT,
        `expense_title` VARCHAR(150) NOT NULL,
        `category` VARCHAR(100) NOT NULL,
        `amount` DECIMAL(12,2) NOT NULL,
        `expense_date` DATE NOT NULL,
        `payment_method` VARCHAR(50) NOT NULL DEFAULT 'Cash',
        `notes` TEXT,
        `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
        `updated_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS `staff` (
        `id` INT NOT NULL AUTO_INCREMENT,
        `staff_code` VARCHAR(30) NOT NULL,
        `staff_name` VARCHAR(150) NOT NULL,
        `designation` VARCHAR(100) NOT NULL,
        `joining_date` DATE NOT NULL,
        `basic_salary` DECIMAL(12,2) NOT NULL DEFAULT '0.00',
        `status` ENUM('Active','Inactive') NOT NULL DEFAULT 'Active',
        `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
        `updated_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        UNIQUE KEY `staff_code` (`staff_code`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS `staff_attendance` (
        `id` INT NOT NULL AUTO_INCREMENT,
        `staff_id` INT NOT NULL,
        `attendance_date` DATE NOT NULL,
        `attendance_status` ENUM('Present','Absent','Late','Leave') NOT NULL DEFAULT 'Present',
        `notes` VARCHAR(255) DEFAULT NULL,
        `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        UNIQUE KEY `unique_staff_attendance` (`staff_id`,`attendance_date`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS `staff_salaries` (
        `id` INT NOT NULL AUTO_INCREMENT,
        `staff_id` INT NOT NULL,
        `salary_month` CHAR(7) NOT NULL,
        `basic_salary` DECIMAL(12,2) NOT NULL DEFAULT '0.00',
        `bonus` DECIMAL(12,2) NOT NULL DEFAULT '0.00',
        `deductions` DECIMAL(12,2) NOT NULL DEFAULT '0.00',
        `paid_amount` DECIMAL(12,2) NOT NULL DEFAULT '0.00',
        `payment_date` DATE DEFAULT NULL,
        `notes` VARCHAR(255) DEFAULT NULL,
        `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
        `updated_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        UNIQUE KEY `unique_staff_salary_month` (`staff_id`,`salary_month`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS `payments` (
        `id` INT NOT NULL AUTO_INCREMENT,
        `payment_type` ENUM('Customer','Supplier') NOT NULL,
        `party_name` VARCHAR(150) NOT NULL,
        `reference` VARCHAR(100) DEFAULT NULL,
        `amount` DECIMAL(12,2) NOT NULL,
        `payment_method` VARCHAR(30) NOT NULL DEFAULT 'Cash',
        `payment_date` DATE NOT NULL,
        `payment_time` TIME DEFAULT NULL,
        `status` ENUM('Completed','Pending') NOT NULL DEFAULT 'Completed',
        `notes` VARCHAR(255) DEFAULT NULL,
        `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
        `updated_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
]


def init_db(max_retries: int = 5, retry_delay: int = 2):
    """Initialize database tables and seed default admin user.

    Includes retry mechanism for cloud environments (e.g., Railway)
    where database container may take a few moments to become ready.
    """
    connection = None
    for attempt in range(1, max_retries + 1):
        try:
            connection = get_connection()
            break
        except Exception as err:
            print(f"[DB Init] Attempt {attempt}/{max_retries} failed: {err}")
            if attempt < max_retries:
                time.sleep(retry_delay)
            else:
                print("[DB Init] Could not connect to database after maximum retries.")
                return False

    if not connection:
        return False

    try:
        cursor = connection.cursor(dictionary=True)
        try:
            # Create all tables
            for query in TABLE_DEFINITIONS:
                cursor.execute(query)
            connection.commit()

            # Seed default admin if admin table is empty
            cursor.execute("SELECT COUNT(*) AS total FROM admin")
            row = cursor.fetchone()
            if not row or row.get("total", 0) == 0:
                cursor.execute(
                    "INSERT INTO admin (username, password_hash) VALUES (%s, %s)",
                    ("admin", "1234")
                )
                connection.commit()
                print("[DB Init] Default admin created (username: 'admin', password: '1234')")

            print("[DB Init] All database tables initialized successfully.")
            return True
        finally:
            cursor.close()
    finally:
        connection.close()


if __name__ == "__main__":
    init_db()
