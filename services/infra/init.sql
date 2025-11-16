CREATE TABLE customer_segments (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(255) NOT NULL,
    segment VARCHAR(100),
    confidence FLOAT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);