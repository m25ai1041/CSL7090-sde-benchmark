import logging
import sys
import os

def setup_logging() -> None:
    """
    Configures the root logger for the application.
    
    This function sets up a standardized logging format and level,
    removes any default handlers, and adds a stream handler to
    log to stdout (which is captured by Docker/Kubernetes).
    """
    
    # Get the log level from an environment variable, default to INFO
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
    
    # This is a production-ready format.
    LOG_FORMAT = "%(asctime)s - [%(levelname)s] - [%(name)s | %(filename)s:%(lineno)d] - %(message)s"

    # Get the root logger
    logger = logging.getLogger()
    
    # Set the level (with a fallback to INFO if the env var is invalid)
    try:
        logger.setLevel(LOG_LEVEL)
    except ValueError:
        logger.setLevel("INFO")
        logger.warning(f"Invalid LOG_LEVEL '{LOG_LEVEL}'. Defaulting to INFO.")

    # Remove existing handlers (like the default one) to avoid duplicate logs
    if logger.hasHandlers():
        for handler in logger.handlers:
            logger.removeHandler(handler)

    # Create a new stream handler to log to stdout
    handler = logging.StreamHandler(sys.stdout)
    
    # Create and set the formatter
    formatter = logging.Formatter(LOG_FORMAT)
    handler.setFormatter(formatter)
    
    # Add the handler to the root logger
    logger.addHandler(handler)
    
    logger.info(f"Logging configured at level {LOG_LEVEL}")