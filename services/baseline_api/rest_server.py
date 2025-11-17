from flask import Flask, request, jsonify
import os
import sys
import psycopg2
from psycopg2 import pool
import preprocessor
import model
import logging
from logging_config import setup_logging
import uuid
import time

# Configure root logger
setup_logging()

# Module-level logger
logger = logging.getLogger(__name__)

# Database configuration from environment variables
DB_HOST = os.environ.get("DB_HOST")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_NAME = os.environ.get("DB_NAME", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD")

# Configuration from environment
MAX_TEXT_LENGTH = int(os.environ.get("MAX_TEXT_LENGTH", "10000"))
DB_MAX_POOL = int(os.environ.get("DB_MAX_POOL", "10"))
DB_MIN_POOL = int(os.environ.get("DB_MIN_POOL", "1"))
DB_CONN_TIMEOUT = int(os.environ.get("DB_CONN_TIMEOUT", "5"))
MAX_REQUEST_SIZE = int(os.environ.get("MAX_REQUEST_SIZE", "1048576"))  # 1MB default

# Global connection pool (one per Gunicorn worker)
db_pool = None

def init_db_pool():
    """Initialize the database connection pool."""
    global db_pool

    if db_pool is not None:
        return

    try:
        logger.info(
            f"Initializing DB Pool → {DB_HOST}:{DB_PORT} / DB={DB_NAME} "
            f"(min={DB_MIN_POOL}, max={DB_MAX_POOL}, timeout={DB_CONN_TIMEOUT}s)"
        )

        db_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=DB_MIN_POOL,
            maxconn=DB_MAX_POOL,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            connect_timeout=DB_CONN_TIMEOUT
        )

        logger.info("DB Pool Ready.")

    except Exception as e:
        logger.critical(f"Failed to initialize DB pool: {e}", exc_info=True)
        sys.exit(1)


def init_schema():
    """Create the database table if it doesn't exist."""
    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS customer_segments (
                    id SERIAL PRIMARY KEY,
                    customer_id VARCHAR(255) NOT NULL,
                    segment VARCHAR(100),
                    confidence FLOAT,
                    processed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Create index for better query performance
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_customer_id 
                ON customer_segments(customer_id, processed_at DESC);
            """)
            
            conn.commit()
        logger.info("Schema initialized successfully.")
    except Exception as e:
        logger.error(f"Schema initialization failed: {e}", exc_info=True)
    finally:
        if conn:
            db_pool.putconn(conn)


# Initialize Flask app
app = Flask(__name__)

# Enforce max request size
app.config['MAX_CONTENT_LENGTH'] = MAX_REQUEST_SIZE

# Initialize DB pool and schema at startup
init_db_pool()
init_schema()
logger.info("Worker ready.")


@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200


@app.route("/classify", methods=["POST"])
def classify():
    """
    Main classification endpoint.
    """
    # Generate request ID for tracing
    request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
    start_time = time.time()
    
    logger.info(f"[{request_id}] New request received")
    
    # Validate JSON payload exists
    data = request.json
    if data is None:
        logger.warning(f"[{request_id}] No JSON payload received")
        return jsonify({"error": "No JSON payload received"}), 400

    # Validate required fields exist
    if "customer_id" not in data or "review_text" not in data:
        logger.warning(f"[{request_id}] Missing required fields: customer_id or review_text")
        return jsonify({"error": "Missing 'customer_id' or 'review_text'"}), 400

    customer_id = data["customer_id"]
    review_text = data["review_text"]

    # Type validation - REJECT invalid types (don't coerce)
    if not isinstance(customer_id, str) or not isinstance(customer_id, str):
        logger.warning(
            f"[{request_id}] Type validation failed: "
            f"customer_id type={type(customer_id).__name__}, "
            f"review_text type={type(review_text).__name__}"
        )
        return jsonify({"error": "customer_id and review_text must be strings"}), 400

    # Validate customer_id is not empty
    if not customer_id or not customer_id.strip():
        logger.warning(f"[{request_id}] Empty or whitespace customer_id")
        return jsonify({"error": "customer_id cannot be empty"}), 400

    # Validate review_text is not empty
    if not review_text or not review_text.strip():
        logger.warning(f"[{request_id}] Empty or whitespace review_text")
        return jsonify({"error": "review_text cannot be empty"}), 400

    # Validate review_text size
    if len(review_text) > MAX_TEXT_LENGTH:
        logger.warning(
            f"[{request_id}] review_text exceeds max length: "
            f"{len(review_text)} > {MAX_TEXT_LENGTH}"
        )
        return jsonify({
            "error": f"review_text exceeds maximum length of {MAX_TEXT_LENGTH} characters"
        }), 400

    logger.info(
        f"[{request_id}] Processing request → "
        f"customer={customer_id}, text_length={len(review_text)}"
    )

    # Step 1: Text Preprocessing (Pure Python)
    try:
        cleaned = preprocessor.clean_text(review_text)
        logger.debug(f"[{request_id}] Preprocessing complete, cleaned_length={len(cleaned)}")
    except Exception as e:
        logger.error(f"[{request_id}] Preprocessing failed: {e}", exc_info=True)
        return jsonify({"error": "Text preprocessing failed"}), 500

    # Step 2: ML Model Inference
    try:
        segment, confidence = model.get_classification(cleaned)
        logger.debug(
            f"[{request_id}] Model inference complete: "
            f"segment={segment}, confidence={confidence:.4f}"
        )
    except Exception as e:
        logger.error(f"[{request_id}] Model inference failed: {e}", exc_info=True)
        return jsonify({"error": "Model classification failed"}), 500

    # Step 3 & 4: Database Operations (Write + Read)
    conn = None
    try:
        # Get connection with timeout
        try:
            conn = db_pool.getconn()
        except pool.PoolError as e:
            logger.error(f"[{request_id}] Failed to get DB connection (pool exhausted): {e}")
            return jsonify({"error": "Database connection unavailable"}), 503
        
        # Write: Insert new classification result
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO customer_segments
                (customer_id, segment, confidence)
                VALUES (%s, %s, %s)
            """, (customer_id, segment, confidence))
            conn.commit()
        
        logger.debug(f"[{request_id}] Inserted classification for customer={customer_id}")

        # Read: Get customer's recent classification history
        with conn.cursor() as cur:
            cur.execute("""
                SELECT processed_at, segment, confidence
                FROM customer_segments
                WHERE customer_id = %s
                ORDER BY processed_at DESC
                LIMIT 5
            """, (customer_id,))
            recent_rows = cur.fetchall()
        
        logger.debug(
            f"[{request_id}] Retrieved {len(recent_rows)} recent classifications "
            f"for customer={customer_id}"
        )

    except psycopg2.OperationalError as e:
        logger.error(f"[{request_id}] DB connection error: {e}", exc_info=True)
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return jsonify({"error": "Database connection failed"}), 503
    
    except psycopg2.ProgrammingError as e:
        logger.error(f"[{request_id}] DB programming error: {e}", exc_info=True)
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return jsonify({"error": "Database query failed"}), 500
    
    except Exception as e:
        logger.error(f"[{request_id}] Unexpected DB error: {e}", exc_info=True)
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return jsonify({"error": "Database operation failed"}), 500
    
    finally:
        if conn:
            db_pool.putconn(conn)

    # Build classification history for response
    history = []
    if recent_rows:
        for row in recent_rows:
            history.append({
                "timestamp": row[0].isoformat(),
                "segment": row[1],
                "confidence": float(row[2])
            })

    processing_time_ms = (time.time() - start_time) * 1000
    
    # Return response
    response = jsonify({
        "request_id": request_id,
        "customer_id": customer_id,
        "classification": segment,
        "confidence": confidence,
        "history_count": len(history),
        "recent_classifications": history[:2],
        "processing_time_ms": round(processing_time_ms, 2)
    })
    
    logger.info(
        f"[{request_id}] Request completed successfully in {processing_time_ms:.2f}ms"
    )
    
    return response, 200


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle 413 - Request Entity Too Large."""
    logger.warning(f"Request exceeded max size of {MAX_REQUEST_SIZE} bytes")
    return jsonify({
        "error": f"Request payload exceeds maximum size of {MAX_REQUEST_SIZE} bytes"
    }), 413


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    logger.warning(f"404 Not Found: {request.path}")
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}", exc_info=True)
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    logger.info(f"Starting Flask development server (debug={debug_mode})...")
    app.run(host="0.0.0.0", port=8000, debug=debug_mode)