import grpc
from concurrent import futures
import logging
import os
import sys
import psycopg2
from psycopg2 import pool
import time
import uuid
import classifier_pb2
import classifier_pb2_grpc
import optimizer
import model

from logging_config import setup_logging
setup_logging()
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
MAX_WORKER_THREADS = int(os.environ.get("MAX_WORKER_THREADS", "4"))

# Global connection pool (one per server)
db_pool = None


def init_db_pool():
    """
    Initialize the database connection pool.
    """
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


class ClassifierServicer(classifier_pb2_grpc.ClassifierServicer):
    """
    gRPC Classification Service Implementation with Database Operations.
    """

    def Classify(
        self,
        request: classifier_pb2.ClassificationRequest,
        context: grpc.ServicerContext
    ) -> classifier_pb2.ClassificationResponse:
        """
        Process a classification request and return an optimized response.
        """

        # Generate request ID for tracing
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        logger.info(f"[{request_id}] gRPC request received for customer: {request.customer_id}")
        customer_id = request.customer_id
        review_text = request.review_text

        # Validate customer_id
        if not customer_id or not isinstance(customer_id, str):
            error_msg = "customer_id must be a non-empty string"
            logger.warning(f"[{request_id}] Validation error: {error_msg}")
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, error_msg)

        if not customer_id.strip():
            error_msg = "customer_id cannot be empty or whitespace"
            logger.warning(f"[{request_id}] Validation error: {error_msg}")
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, error_msg)

        # Validate review_text
        if not review_text or not isinstance(review_text, str):
            error_msg = "review_text must be a non-empty string"
            logger.warning(f"[{request_id}] Validation error: {error_msg}")
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, error_msg)

        if not review_text.strip():
            error_msg = "review_text cannot be empty or whitespace"
            logger.warning(f"[{request_id}] Validation error: {error_msg}")
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, error_msg)

        # Validate review_text size
        if len(review_text) > MAX_TEXT_LENGTH:
            error_msg = f"review_text exceeds maximum length of {MAX_TEXT_LENGTH} characters"
            logger.warning(f"[{request_id}] Validation error: {error_msg}")
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, error_msg)

        logger.info(
            f"[{request_id}] Validation passed → customer={customer_id}, "
            f"text_length={len(review_text)}"
        )

        try:
            cleaned_text = optimizer.clean_text(review_text)
            logger.debug(f"[{request_id}] Preprocessing complete, cleaned_length={len(cleaned_text)}")
        except Exception as e:
            logger.error(f"[{request_id}] Text preprocessing failed: {e}", exc_info=True)
            context.abort(grpc.StatusCode.INTERNAL, "Text preprocessing failed")

        try:
            segment, confidence = model.get_classification(cleaned_text)
            logger.debug(
                f"[{request_id}] Model inference complete: "
                f"segment={segment}, confidence={confidence:.4f}"
            )
        except Exception as e:
            logger.error(f"[{request_id}] Model inference failed: {e}", exc_info=True)
            context.abort(grpc.StatusCode.INTERNAL, "Model classification failed")

        conn = None
        try:
            # Get connection with timeout
            try:
                conn = db_pool.getconn()
            except pool.PoolError as e:
                logger.error(f"[{request_id}] Failed to get DB connection (pool exhausted): {e}")
                context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Database connection unavailable")

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
            context.abort(grpc.StatusCode.UNAVAILABLE, "Database connection failed")

        except psycopg2.ProgrammingError as e:
            logger.error(f"[{request_id}] DB programming error: {e}", exc_info=True)
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            context.abort(grpc.StatusCode.INTERNAL, "Database query failed")

        except Exception as e:
            logger.error(f"[{request_id}] Unexpected DB error: {e}", exc_info=True)
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            context.abort(grpc.StatusCode.INTERNAL, "Database operation failed")

        finally:
            if conn:
                db_pool.putconn(conn)

        history_entries = []
        if recent_rows:
            for row in recent_rows:
                history_entry = classifier_pb2.HistoryEntry(
                    timestamp=row[0].isoformat(),
                    segment=row[1],
                    confidence=float(row[2])
                )
                history_entries.append(history_entry)

        processing_time_ms = (time.time() - start_time) * 1000

        response = classifier_pb2.ClassificationResponse(
            request_id=request_id,
            customer_id=customer_id,
            segment=segment,
            confidence=confidence,
            history_count=len(history_entries),
            recent_classifications=history_entries[:2],
            processing_time_ms=processing_time_ms
        )

        logger.info(
            f"[{request_id}] Request completed successfully in {processing_time_ms:.2f}ms"
        )

        return response


def serve() -> None:
    """
    Start the gRPC classification server with database support.
    -----
    RPC endpoint: 0.0.0.0:50051
    """
    # Initialize database
    init_db_pool()
    init_schema()

    # Create gRPC server with configurable worker threads
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=MAX_WORKER_THREADS))

    classifier_pb2_grpc.add_ClassifierServicer_to_server(
        ClassifierServicer(),
        server
    )

    server.add_insecure_port('[::]:50051')
    logger.info(
        f"Starting gRPC server on port 50051 with {MAX_WORKER_THREADS} worker threads..."
    )

    server.start()

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Stopping gRPC server...")
        server.stop(0)


if __name__ == '__main__':
    serve()