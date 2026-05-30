CREATE TABLE orders (
    id           UUID PRIMARY KEY,
    total        NUMERIC(19,4) NOT NULL CHECK (total >= 0),
    placed_at    TIMESTAMP WITH TIME ZONE NOT NULL,
    status       VARCHAR(16) NOT NULL DEFAULT 'PLACED'
);

CREATE INDEX idx_orders_placed_at ON orders(placed_at);
