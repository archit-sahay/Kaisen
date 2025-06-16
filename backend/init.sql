-- Database initialization for OSRS Price Tracker
-- This file is executed automatically when PostgreSQL container starts

-- Create items table (relatively static data from mapping API)
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    examine TEXT,
    members BOOLEAN DEFAULT false,
    lowalch INTEGER,
    highalch INTEGER,
    limit_value INTEGER, -- renamed from 'limit' (SQL reserved word)
    value INTEGER,
    icon VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create prices table (frequently updated data from latest API)
CREATE TABLE IF NOT EXISTS prices (
    item_id INTEGER PRIMARY KEY REFERENCES items(id),
    high_price INTEGER,
    high_time BIGINT, -- Unix timestamp
    low_price INTEGER,
    low_time BIGINT,  -- Unix timestamp
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_items_name ON items(name);
CREATE INDEX IF NOT EXISTS idx_items_members ON items(members);
CREATE INDEX IF NOT EXISTS idx_items_updated ON items(updated_at);

CREATE INDEX IF NOT EXISTS idx_prices_item_id ON prices(item_id);
CREATE INDEX IF NOT EXISTS idx_prices_updated ON prices(last_updated);
CREATE INDEX IF NOT EXISTS idx_prices_high_time ON prices(high_time);
CREATE INDEX IF NOT EXISTS idx_prices_low_time ON prices(low_time);

-- Create a view for easy joining of items with their latest prices
CREATE OR REPLACE VIEW items_with_prices AS
SELECT 
    i.id,
    i.name,
    i.examine,
    i.members,
    i.lowalch,
    i.highalch,
    i.limit_value,
    i.value,
    i.icon,
    i.created_at,
    i.updated_at,
    p.high_price,
    p.high_time,
    p.low_price,
    p.low_time,
    p.last_updated as price_last_updated
FROM items i
LEFT JOIN prices p ON i.id = p.item_id;

-- Insert some sample data for testing (optional)
-- This will be replaced by actual data from OSRS APIs
INSERT INTO items (id, name, examine, members, lowalch, highalch, value) VALUES
(1, 'Sample Item', 'A sample item for testing', false, 100, 150, 200)
ON CONFLICT (id) DO NOTHING; 