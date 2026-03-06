**users**
- id: UUID (PK)
- clerk_id: VARCHAR (UNIQUE)
- email: VARCHAR (UNIQUE)
- full_name: VARCHAR
- role: ENUM ('user', 'admin') — default 'user'
- avatar_url: TEXT (nullable)
- address: JSONB (nullable — stores street, city, state, zip)
- created_at: TIMESTAMPTZ (default: now())

**categories**
- id: UUID (PK)
- name: VARCHAR
- description: TEXT (nullable)
- created_at: TIMESTAMPTZ (default: now())

**products**
- id: UUID (PK)
- category_id: UUID (FK → categories.id)
- name: VARCHAR
- description: TEXT
- price: DECIMAL(10,2)
- image_url: TEXT (nullable)
- tags: TEXT[] (array of dietary tags: vegan, gluten-free, etc.)
- is_available: BOOLEAN (default: true)
- created_at: TIMESTAMPTZ (default: now())

**promos**
- id: UUID (PK)
- code: VARCHAR (UNIQUE)
- discount_pct: DECIMAL(5,2) (e.g., 10.00 for 10%)
- max_uses: INTEGER (nullable — null = unlimited)
- used_count: INTEGER (default: 0)
- expires_at: TIMESTAMPTZ (nullable)
- is_active: BOOLEAN (default: true)
- created_at: TIMESTAMPTZ (default: now())

**orders**
- id: UUID (PK)
- user_id: UUID (FK → users.id)
- status: ENUM ('pending', 'processing', 'delivered', 'cancelled') — default 'pending'
- total_amount: DECIMAL(10,2)
- promo_id: UUID (FK → promos.id, nullable)
- stripe_session_id: VARCHAR (nullable)
- delivery_address: JSONB (snapshot of address at order time)
- created_at: TIMESTAMPTZ (default: now())

**order_items**
- id: UUID (PK)
- order_id: UUID (FK → orders.id)
- product_id: UUID (FK → products.id)
- quantity: INTEGER (default: 1)
- unit_price: DECIMAL(10,2) (price at time of order)
- customizations: JSONB (nullable — e.g., {"extra_cheese": true, "no_onions": true})

**payments**
- id: UUID (PK)
- order_id: UUID (FK → orders.id) (UNIQUE — one payment per order)
- stripe_payment_id: VARCHAR (UNIQUE)
- amount: DECIMAL(10,2)
- status: ENUM ('succeeded', 'failed', 'refunded') — default 'succeeded'
- refunded_at: TIMESTAMPTZ (nullable)
- created_at: TIMESTAMPTZ (default: now())

**reviews**
- id: UUID (PK)
- user_id: UUID (FK → users.id)
- product_id: UUID (FK → products.id)
- order_id: UUID (FK → orders.id) (to verify purchase)
- rating: SMALLINT (check: rating >= 1 AND rating <= 5)
- body: TEXT (nullable)
- created_at: TIMESTAMPTZ (default: now())

**predictions** (caches ML results)
- id: UUID (PK)
- model_name: VARCHAR
- model_version: VARCHAR
- entity_type: ENUM ('user', 'product')
- entity_id: UUID (not a FK — can point to any entity)
- prediction: JSONB (stores the prediction result)
- created_at: TIMESTAMPTZ (default: now())

**customer_segments** (RFM + churn)
- id: UUID (PK)
- user_id: UUID (FK → users.id) (UNIQUE)
- segment: VARCHAR ('champion', 'loyal', 'at_risk', 'lost', 'new')
- rfm_score: JSONB (stores recency/frequency/monetary scores)
- churn_prob: DECIMAL(5,4) (nullable — 0.0000 to 1.0000)
- updated_at: TIMESTAMPTZ (default: now())

**audit_log** (anomaly detection + system events)
- id: UUID (PK)
- event_type: VARCHAR (e.g., 'anomaly', 'order_flag', 'system_error')
- entity_id: UUID (nullable — which order/user triggered this)
- anomaly_score: DECIMAL(5,4) (nullable)
- metadata: JSONB (additional context)
- created_at: TIMESTAMPTZ (default: now())


