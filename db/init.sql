CREATE SCHEMA IF NOT EXISTS products;
CREATE SCHEMA IF NOT EXISTS payments;
CREATE SCHEMA IF NOT EXISTS couriers;
CREATE SCHEMA IF NOT EXISTS notifications;

CREATE TABLE IF NOT EXISTS products.categories (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products.products (
    id BIGSERIAL PRIMARY KEY,
    category_id BIGINT NOT NULL REFERENCES products.categories(id),
    name TEXT NOT NULL,
    price NUMERIC(10,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS products.customers (
    id BIGSERIAL PRIMARY KEY,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products.orders (
    id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES products.customers(id),
    total_amount NUMERIC(10,2) NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'created',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS products.order_items (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES products.orders(id),
    product_id BIGINT NOT NULL REFERENCES products.products(id),
    quantity INT NOT NULL DEFAULT 1,
    price NUMERIC(10,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS payments.payments (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL,
    amount NUMERIC(10,2) NOT NULL,
    status TEXT NOT NULL DEFAULT 'paid',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS couriers.couriers (
    id BIGSERIAL PRIMARY KEY,
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS couriers.deliveries (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL,
    courier_id BIGINT NOT NULL REFERENCES couriers.couriers(id),
    address TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'assigned',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS notifications.notifications (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL,
    channel TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'sent',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO products.categories(name)
SELECT 'Category ' || gs
FROM generate_series(1, 100) gs
ON CONFLICT DO NOTHING;

INSERT INTO products.products(category_id, name, price)
SELECT ((gs - 1) % 100) + 1, 'Product ' || gs, ROUND((50 + gs * 1.75)::numeric, 2)
FROM generate_series(1, 200) gs
ON CONFLICT DO NOTHING;

INSERT INTO products.customers(full_name, email)
SELECT 'Customer ' || gs, 'customer' || gs || '@example.com'
FROM generate_series(1, 150) gs
ON CONFLICT DO NOTHING;

INSERT INTO products.orders(customer_id, total_amount, status, created_at)
SELECT ((gs - 1) % 150) + 1, ROUND((200 + gs * 3.10)::numeric, 2), 'seeded', NOW() - (gs || ' hours')::interval
FROM generate_series(1, 120) gs
ON CONFLICT DO NOTHING;

INSERT INTO products.order_items(order_id, product_id, quantity, price)
SELECT o.id, ((o.id - 1) % 200) + 1, 1, p.price
FROM products.orders o
JOIN products.products p ON p.id = ((o.id - 1) % 200) + 1
UNION ALL
SELECT o.id, ((o.id + 10 - 1) % 200) + 1, 1, p.price
FROM products.orders o
JOIN products.products p ON p.id = ((o.id + 10 - 1) % 200) + 1
ON CONFLICT DO NOTHING;

INSERT INTO payments.payments(order_id, amount, status, created_at)
SELECT id, total_amount, 'paid', created_at
FROM products.orders
ON CONFLICT DO NOTHING;

INSERT INTO couriers.couriers(full_name, phone)
SELECT 'Courier ' || gs, '+1000000' || LPAD(gs::text, 4, '0')
FROM generate_series(1, 120) gs
ON CONFLICT DO NOTHING;

INSERT INTO couriers.deliveries(order_id, courier_id, address, status, created_at)
SELECT o.id, ((o.id - 1) % 120) + 1, 'Seed address ' || o.id, 'delivered', o.created_at
FROM products.orders o
ON CONFLICT DO NOTHING;

INSERT INTO notifications.notifications(order_id, channel, message, status, created_at)
SELECT o.id, 'email', 'Seed notification for order ' || o.id, 'sent', o.created_at
FROM products.orders o
ON CONFLICT DO NOTHING;
