-- Shop Management Software Database Schema
-- Compatible with MySQL 8.0+

CREATE DATABASE IF NOT EXISTS `shop_management` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `shop_management`;

-- 1. Admin Table
CREATE TABLE IF NOT EXISTS `admin` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(50) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Customers Table
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

-- 3. Suppliers Table
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

-- 4. Products Table
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

-- 5. Purchases Table
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

-- 6. Purchase Items Table
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

-- 7. Sales Table
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

-- 8. Sale Items Table
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

-- 9. Sales Returns Table
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

-- 10. Sales Return Items Table
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

-- 11. Customer Credit Transactions Table
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

-- 12. Expenses Table
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

-- 13. Staff Table
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

-- 14. Staff Attendance Table
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

-- 15. Staff Salaries Table
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

-- 16. Payments Table
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

-- Default Admin User (admin / 1234)
INSERT INTO `admin` (`id`, `username`, `password_hash`)
SELECT 1, 'admin', '1234'
WHERE NOT EXISTS (SELECT 1 FROM `admin` WHERE `username` = 'admin');
