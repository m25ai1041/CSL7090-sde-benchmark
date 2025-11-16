from flask import Flask, request, jsonify
import logging
import sys
import preprocessor
import model


try:
    from logging_config import setup_logging
    setup_logging()
except ImportError:
    logging.basicConfig(stream=sys.stdout, 
                        level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s")

logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route("/classify", methods=['POST'])
def classify():
    """
    This is the "Basic" endpoint using Flask.
    It uses a slow, pure-Python preprocessor.
    
    Input:  JSON payload
    Output: JSON payload
    """
    try:
        data = request.json
        if not data:
            logger.warning("No JSON payload received.")
            return jsonify({"error": "No JSON payload received"}), 400

        customer_id = data.get('customer_id')
        review_text = data.get('review_text')

        if not customer_id or not review_text:
            logger.warning("Missing 'customer_id' or 'review_text' in request")
            return jsonify({"error": "Missing 'customer_id' or 'review_text'"}), 400

        logger.info(f"Received REST request for customer: {customer_id}")
        
        cleaned_text = preprocessor.clean_text(review_text)
        segment, confidence = model.get_classification(cleaned_text)
        
        logger.info(f"Successfully classified customer: {customer_id}")
        
        response = {
            "customer_id": customer_id,
            "segment": segment,
            "confidence": confidence
        }
        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error during classification for customer {customer_id}: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    logger.info("Starting 'Basic' Flask server in DEBUG mode on port 8000...")
    app.run(host="0.0.0.0", port=8000, debug=True)