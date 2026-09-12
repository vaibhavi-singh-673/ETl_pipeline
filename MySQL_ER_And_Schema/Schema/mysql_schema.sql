-- RetailMart operational schema
-- MySQL 8.0+
CREATE DATABASE IF NOT EXISTS retailmart;
USE retailmart;

CREATE TABLE categories (
    category_id INT UNSIGNED NOT NULL,
    category_name VARCHAR(100) NOT NULL,
    description VARCHAR(500),
    PRIMARY KEY (category_id),
    UNIQUE KEY uq_categories_name (category_name)
) ENGINE=InnoDB;

CREATE TABLE products (
    product_id INT UNSIGNED NOT NULL,
    product_name VARCHAR(200) NOT NULL,
    category_id INT UNSIGNED NOT NULL,
    unit_price DECIMAL(12,2) NOT NULL,
    cost_price DECIMAL(12,2) NOT NULL,
    stock_quantity INT NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (product_id),
    CONSTRAINT fk_products_category
        FOREIGN KEY (category_id) REFERENCES categories(category_id),
    CONSTRAINT chk_products_unit_price CHECK (unit_price >= 0),
    CONSTRAINT chk_products_cost_price CHECK (cost_price >= 0),
    CONSTRAINT chk_products_stock CHECK (stock_quantity >= 0)
) ENGINE=InnoDB;

CREATE TABLE customers (
    customer_id INT UNSIGNED NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(30),
    city VARCHAR(100),
    registration_date DATE NOT NULL,
    loyalty_tier VARCHAR(30),
    PRIMARY KEY (customer_id),
    UNIQUE KEY uq_customers_email (email)
) ENGINE=InnoDB;

CREATE TABLE sales_transactions (
    transaction_id BIGINT UNSIGNED NOT NULL,
    customer_id INT UNSIGNED NULL,
    store_id INT UNSIGNED NOT NULL,
    transaction_date DATE NOT NULL,
    transaction_time TIME NOT NULL,
    payment_method VARCHAR(30) NOT NULL,
    total_amount DECIMAL(14,2) NOT NULL,
    discount_amount DECIMAL(14,2) NOT NULL DEFAULT 0,
    tax_amount DECIMAL(14,2) NOT NULL DEFAULT 0,
    net_amount DECIMAL(14,2) NOT NULL,
    PRIMARY KEY (transaction_id),
    KEY idx_sales_date (transaction_date),
    KEY idx_sales_customer (customer_id),
    KEY idx_sales_store (store_id),
    CONSTRAINT fk_sales_customer
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    CONSTRAINT chk_sales_amounts CHECK (
        total_amount >= 0 AND discount_amount >= 0 AND tax_amount >= 0 AND net_amount >= 0
    )
) ENGINE=InnoDB;

CREATE TABLE sales_items (
    item_id BIGINT UNSIGNED NOT NULL,
    transaction_id BIGINT UNSIGNED NOT NULL,
    product_id INT UNSIGNED NOT NULL,
    quantity INT UNSIGNED NOT NULL,
    unit_price DECIMAL(12,2) NOT NULL,
    line_total DECIMAL(14,2) NOT NULL,
    PRIMARY KEY (item_id),
    KEY idx_items_transaction (transaction_id),
    KEY idx_items_product (product_id),
    CONSTRAINT fk_items_transaction
        FOREIGN KEY (transaction_id) REFERENCES sales_transactions(transaction_id),
    CONSTRAINT fk_items_product
        FOREIGN KEY (product_id) REFERENCES products(product_id),
    CONSTRAINT chk_items_quantity CHECK (quantity > 0),
    CONSTRAINT chk_items_price CHECK (unit_price >= 0),
    CONSTRAINT chk_items_total CHECK (line_total >= 0)
) ENGINE=InnoDB;

CREATE TABLE vouchers (
    voucher_id INT UNSIGNED NOT NULL,
    voucher_code VARCHAR(50) NOT NULL,
    voucher_type VARCHAR(20) NOT NULL,
    discount_value DECIMAL(12,2) NOT NULL,
    min_purchase_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
    max_discount_amount DECIMAL(12,2) NULL,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (voucher_id),
    UNIQUE KEY uq_vouchers_code (voucher_code),
    CONSTRAINT chk_voucher_dates CHECK (valid_to >= valid_from)
) ENGINE=InnoDB;

CREATE TABLE voucher_redemptions (
    redemption_id BIGINT UNSIGNED NOT NULL,
    voucher_id INT UNSIGNED NOT NULL,
    transaction_id BIGINT UNSIGNED NOT NULL,
    customer_id INT UNSIGNED NOT NULL,
    redemption_date DATE NOT NULL,
    discount_applied DECIMAL(14,2) NOT NULL DEFAULT 0,
    PRIMARY KEY (redemption_id),
    UNIQUE KEY uq_voucher_transaction (voucher_id, transaction_id),
    KEY idx_redemption_date (redemption_date),
    CONSTRAINT fk_redemption_voucher
        FOREIGN KEY (voucher_id) REFERENCES vouchers(voucher_id),
    CONSTRAINT fk_redemption_transaction
        FOREIGN KEY (transaction_id) REFERENCES sales_transactions(transaction_id),
    CONSTRAINT fk_redemption_customer
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
) ENGINE=InnoDB;

CREATE TABLE returns (
    return_id BIGINT UNSIGNED NOT NULL,
    transaction_id BIGINT UNSIGNED NOT NULL,
    item_id BIGINT UNSIGNED NOT NULL,
    customer_id INT UNSIGNED NOT NULL,
    product_id INT UNSIGNED NOT NULL,
    return_date DATE NOT NULL,
    return_quantity INT UNSIGNED NOT NULL,
    return_reason VARCHAR(100) NOT NULL,
    refund_amount DECIMAL(14,2) NOT NULL,
    refund_status VARCHAR(30) NOT NULL,
    PRIMARY KEY (return_id),
    KEY idx_returns_date (return_date),
    KEY idx_returns_product (product_id),
    KEY idx_returns_transaction (transaction_id),
    CONSTRAINT fk_returns_transaction
        FOREIGN KEY (transaction_id) REFERENCES sales_transactions(transaction_id),
    CONSTRAINT fk_returns_item
        FOREIGN KEY (item_id) REFERENCES sales_items(item_id),
    CONSTRAINT fk_returns_customer
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    CONSTRAINT fk_returns_product
        FOREIGN KEY (product_id) REFERENCES products(product_id),
    CONSTRAINT chk_returns_quantity CHECK (return_quantity > 0),
    CONSTRAINT chk_returns_refund CHECK (refund_amount >= 0)
) ENGINE=InnoDB;
