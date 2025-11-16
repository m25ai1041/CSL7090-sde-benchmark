import logging
import random
import time
from typing import Tuple

# --- Get Logger ---
logger = logging.getLogger(__name__)

logger.info("--- LOADING MOCK ML MODEL (LIGHTWEIGHT) ---")

# --- The function your APIs will call ---
def get_classification(text: str) -> Tuple[str, float]:
    """
    This is a MOCK function that simulates the ML pipeline.
    
    It has no heavy dependencies (no torch, no transformers).
    It uses simple keyword logic and returns the correct format.
    
    Input:  text (str)
    Output: tuple (segment: str, confidence: float)
    """
    logger.info(f"Mock Model: Classifying text: '{text[:20]}...'")
    
    # 1. Define segments
    segments = ["High-Value", "Mid-Value", "At-Risk"]
    
    # 2. Simple keyword-based logic
    text_lower = text.lower()
    
    if any(word in text_lower for word in ["great", "fantastic", "love", "happy", "excellent"]):
        segment = "High-Value"
        confidence = random.uniform(0.85, 0.99)
    elif any(word in text_lower for word in ["terrible", "bad", "unhappy", "problem", "hate"]):
        segment = "At-Risk"
        confidence = random.uniform(0.75, 0.95)
    else:
        segment = "Mid-Value"
        confidence = random.uniform(0.50, 0.80)
        
    logger.info(f"Mock Model: Classification complete ({segment})")
    
    # 4. Return in the exact same format
    return segment, round(confidence, 4)

if __name__ == "__main__":
    # If we run this file directly, setup a basic logger for testing
    try:
        from logging_config import setup_logging
        setup_logging()
    except ImportError:
        logging.basicConfig(level=logging.INFO)
    
    segment, conf = get_classification("This is a great product!")
    logger.info(f"Test Classification 1: {segment} (Confidence: {conf:.4f})")
    
    segment, conf = get_classification("I have a problem with my order.")
    logger.info(f"Test Classification 2: {segment} (Confidence: {conf:.4f})")
    
    segment, conf = get_classification("The product is okay.")
    logger.info(f"Test Classification 3: {segment} (Confidence: {conf:.4f})")