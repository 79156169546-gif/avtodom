-- Схема БД «Витрина заказов 24/7» (Neon PostgreSQL).
-- Применяется через backend/scripts/apply_schema.py (идемпотентно).

-- Каталог ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    id               SERIAL PRIMARY KEY,
    sku              TEXT UNIQUE NOT NULL,
    name             TEXT NOT NULL,
    brand            TEXT,
    category         TEXT,
    price            NUMERIC(12,2) NOT NULL CHECK (price >= 0),
    old_price        NUMERIC(12,2),
    discount_percent INTEGER NOT NULL DEFAULT 0 CHECK (discount_percent >= 0 AND discount_percent <= 90),
    image_url        TEXT,
    in_stock         BOOLEAN NOT NULL DEFAULT TRUE,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    description      TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Деталь «под заказ»: её заказываем у поставщика, срок — order_days дней.
ALTER TABLE products ADD COLUMN IF NOT EXISTS is_on_order BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE products ADD COLUMN IF NOT EXISTS order_days INTEGER NOT NULL DEFAULT 3
    CHECK (order_days >= 0 AND order_days <= 365);

-- Пользователи и сессии -------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name     TEXT,
    phone         TEXT,
    telegram      TEXT,
    role          TEXT NOT NULL DEFAULT 'customer' CHECK (role IN ('customer','owner')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id);

-- Заказы ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    id              SERIAL PRIMARY KEY,
    order_number    TEXT UNIQUE NOT NULL,
    user_id         INTEGER REFERENCES users(id) ON DELETE SET NULL,
    customer_name   TEXT NOT NULL,
    phone           TEXT,
    telegram        TEXT,
    car_make        TEXT,
    car_model       TEXT,
    vin             TEXT,
    pickup_method   TEXT NOT NULL CHECK (pickup_method IN ('pickup','delivery')),
    address         TEXT,
    comment         TEXT,
    total           NUMERIC(12,2) NOT NULL,
    is_night_order  BOOLEAN NOT NULL DEFAULT FALSE,
    -- В заказе есть позиции «под заказ» — их ждём от поставщика.
    has_on_order    BOOLEAN NOT NULL DEFAULT FALSE,
    status          TEXT NOT NULL DEFAULT 'new',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);

-- Добавление колонок в уже созданные таблицы (CREATE TABLE IF NOT EXISTS
-- новых колонок в существующих таблицах не добавляет).
ALTER TABLE orders ADD COLUMN IF NOT EXISTS has_on_order BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS order_items (
    id           SERIAL PRIMARY KEY,
    order_id     INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id   INTEGER REFERENCES products(id) ON DELETE SET NULL,
    product_name TEXT NOT NULL,
    price        NUMERIC(12,2) NOT NULL,
    qty          INTEGER NOT NULL DEFAULT 1 CHECK (qty > 0),
    line_total   NUMERIC(12,2) NOT NULL,
    -- Снимок состояния на момент заказа: меняем каталог — история не едет.
    is_on_order  BOOLEAN NOT NULL DEFAULT FALSE,
    order_days   INTEGER NOT NULL DEFAULT 0
);

ALTER TABLE order_items ADD COLUMN IF NOT EXISTS is_on_order BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE order_items ADD COLUMN IF NOT EXISTS order_days INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);

-- История статусов (таймлайн в личном кабинете) --------------------------
CREATE TABLE IF NOT EXISTS order_events (
    id         SERIAL PRIMARY KEY,
    order_id   INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    status     TEXT NOT NULL,
    note       TEXT,
    actor      TEXT NOT NULL DEFAULT 'system',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_order_events_order ON order_events(order_id, id);

-- Кнопки Telegram -> заказ (разбор callback_query) -----------------------
CREATE TABLE IF NOT EXISTS telegram_buttons (
    id         SERIAL PRIMARY KEY,
    order_id   INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    message_id BIGINT NOT NULL,
    action     TEXT NOT NULL,
    label      TEXT NOT NULL,
    used_at    TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_telegram_buttons_order ON telegram_buttons(order_id);

-- Номера заказов --------------------------------------------------------
CREATE SEQUENCE IF NOT EXISTS order_num_seq START 1;
