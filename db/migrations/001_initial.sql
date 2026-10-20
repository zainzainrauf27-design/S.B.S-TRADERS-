CREATE TABLE business_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

INSERT INTO business_settings (setting_key, setting_value, updated_at) VALUES
    ('business_name', 'S.A.B Trader', strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    ('business_type', 'Cosmetics Wholesale & Supply', strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    ('company_phone', '03336447526', strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    ('developer_brand', 'WEB BY ZAINI', strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    ('developer_phone', '03327021212', strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    ('currency', 'PKR', strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    ('timezone', 'Asia/Karachi', strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    ('invoice_prefix', 'INV', strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    ('receipt_width_mm', '80', strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    ('developer_footer_enabled', 'true', strftime('%Y-%m-%dT%H:%M:%fZ','now'));

CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'staff')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    token_hash TEXT NOT NULL UNIQUE,
    device_id TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT
);
CREATE INDEX sessions_user_active ON sessions(user_id, revoked_at, expires_at);

CREATE TABLE categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE brands (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE customers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT,
    address TEXT,
    area TEXT,
    opening_balance_paisa INTEGER NOT NULL DEFAULT 0,
    credit_limit_paisa INTEGER CHECK (credit_limit_paisa IS NULL OR credit_limit_paisa >= 0),
    notes TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_by TEXT REFERENCES users(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX customers_phone ON customers(phone);
CREATE INDEX customers_name ON customers(name COLLATE NOCASE);

CREATE TABLE suppliers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT,
    address TEXT,
    opening_balance_paisa INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX suppliers_name ON suppliers(name COLLATE NOCASE);

CREATE TABLE products (
    id TEXT PRIMARY KEY,
    sku TEXT UNIQUE COLLATE NOCASE,
    barcode TEXT UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    brand_id TEXT REFERENCES brands(id),
    category_id TEXT REFERENCES categories(id),
    description TEXT,
    unit TEXT NOT NULL DEFAULT 'piece',
    purchase_cost_paisa INTEGER NOT NULL DEFAULT 0 CHECK (purchase_cost_paisa >= 0),
    wholesale_price_paisa INTEGER NOT NULL CHECK (wholesale_price_paisa >= 0),
    retail_price_paisa INTEGER CHECK (retail_price_paisa IS NULL OR retail_price_paisa >= 0),
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    minimum_stock INTEGER NOT NULL DEFAULT 0 CHECK (minimum_stock >= 0),
    preferred_supplier_id TEXT REFERENCES suppliers(id),
    batch_number TEXT,
    expiry_date TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX products_name ON products(name COLLATE NOCASE);
CREATE INDEX products_category ON products(category_id, active);
CREATE INDEX products_brand ON products(brand_id, active);

CREATE TABLE purchases (
    id TEXT PRIMARY KEY,
    purchase_number TEXT NOT NULL UNIQUE,
    supplier_id TEXT NOT NULL REFERENCES suppliers(id),
    purchased_at TEXT NOT NULL,
    subtotal_paisa INTEGER NOT NULL CHECK (subtotal_paisa >= 0),
    discount_paisa INTEGER NOT NULL DEFAULT 0 CHECK (discount_paisa >= 0),
    total_paisa INTEGER NOT NULL CHECK (total_paisa >= 0),
    amount_paid_paisa INTEGER NOT NULL DEFAULT 0 CHECK (amount_paid_paisa >= 0),
    status TEXT NOT NULL CHECK (status IN ('posted', 'reversed')),
    notes TEXT,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
);
CREATE INDEX purchases_supplier_date ON purchases(supplier_id, purchased_at);

CREATE TABLE purchase_items (
    id TEXT PRIMARY KEY,
    purchase_id TEXT NOT NULL REFERENCES purchases(id),
    product_id TEXT NOT NULL REFERENCES products(id),
    product_name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_cost_paisa INTEGER NOT NULL CHECK (unit_cost_paisa >= 0),
    line_total_paisa INTEGER NOT NULL CHECK (line_total_paisa >= 0)
);

CREATE TABLE sales (
    id TEXT PRIMARY KEY,
    invoice_number TEXT NOT NULL UNIQUE,
    customer_id TEXT REFERENCES customers(id),
    customer_name_snapshot TEXT NOT NULL,
    customer_phone_snapshot TEXT,
    sold_at TEXT NOT NULL,
    subtotal_paisa INTEGER NOT NULL CHECK (subtotal_paisa >= 0),
    discount_paisa INTEGER NOT NULL DEFAULT 0 CHECK (discount_paisa >= 0),
    total_paisa INTEGER NOT NULL CHECK (total_paisa >= 0),
    status TEXT NOT NULL CHECK (status IN ('posted', 'cancelled', 'returned')),
    staff_id TEXT NOT NULL REFERENCES users(id),
    notes TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX sales_customer_date ON sales(customer_id, sold_at);
CREATE INDEX sales_staff_date ON sales(staff_id, sold_at);

CREATE TABLE sale_items (
    id TEXT PRIMARY KEY,
    sale_id TEXT NOT NULL REFERENCES sales(id),
    product_id TEXT NOT NULL REFERENCES products(id),
    product_name_snapshot TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_paisa INTEGER NOT NULL CHECK (unit_price_paisa >= 0),
    unit_cost_paisa INTEGER NOT NULL CHECK (unit_cost_paisa >= 0),
    discount_paisa INTEGER NOT NULL DEFAULT 0 CHECK (discount_paisa >= 0),
    line_total_paisa INTEGER NOT NULL CHECK (line_total_paisa >= 0)
);
CREATE INDEX sale_items_product ON sale_items(product_id, sale_id);

CREATE TABLE payments (
    id TEXT PRIMARY KEY,
    payment_number TEXT NOT NULL UNIQUE,
    customer_id TEXT REFERENCES customers(id),
    supplier_id TEXT REFERENCES suppliers(id),
    sale_id TEXT REFERENCES sales(id),
    purchase_id TEXT REFERENCES purchases(id),
    amount_paisa INTEGER NOT NULL CHECK (amount_paisa > 0),
    method TEXT NOT NULL,
    paid_at TEXT NOT NULL,
    reversal_of TEXT REFERENCES payments(id),
    note TEXT,
    recorded_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    CHECK ((customer_id IS NOT NULL) OR (supplier_id IS NOT NULL) OR (sale_id IS NOT NULL) OR (purchase_id IS NOT NULL))
);
CREATE INDEX payments_customer_date ON payments(customer_id, paid_at);
CREATE INDEX payments_supplier_date ON payments(supplier_id, paid_at);

CREATE TABLE stock_movements (
    id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES products(id),
    quantity_delta INTEGER NOT NULL CHECK (quantity_delta <> 0),
    unit_cost_paisa INTEGER CHECK (unit_cost_paisa IS NULL OR unit_cost_paisa >= 0),
    reason TEXT NOT NULL,
    source_type TEXT,
    source_id TEXT,
    actor_id TEXT NOT NULL REFERENCES users(id),
    occurred_at TEXT NOT NULL,
    note TEXT
);
CREATE INDEX stock_movements_product_date ON stock_movements(product_id, occurred_at);

CREATE TABLE attendance (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    checked_in_at TEXT NOT NULL,
    checked_out_at TEXT,
    device_id TEXT,
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX attendance_one_open_shift ON attendance(user_id) WHERE checked_out_at IS NULL;
CREATE INDEX attendance_user_date ON attendance(user_id, checked_in_at);

CREATE TABLE sync_operations (
    operation_id TEXT PRIMARY KEY,
    record_id TEXT NOT NULL,
    staff_id TEXT NOT NULL REFERENCES users(id),
    device_id TEXT NOT NULL,
    operation_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'syncing', 'synced', 'failed', 'needs_review')),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    last_error TEXT,
    created_at TEXT NOT NULL,
    processed_at TEXT,
    result_json TEXT
);
CREATE INDEX sync_operations_status_created ON sync_operations(status, created_at);

CREATE TABLE audit_events (
    id TEXT PRIMARY KEY,
    actor_id TEXT REFERENCES users(id),
    action TEXT NOT NULL,
    record_type TEXT NOT NULL,
    record_id TEXT,
    details_json TEXT NOT NULL DEFAULT '{}',
    occurred_at TEXT NOT NULL
);
CREATE INDEX audit_events_record ON audit_events(record_type, record_id, occurred_at);
