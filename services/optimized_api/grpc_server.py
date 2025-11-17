import grpc
from concurrent import futures
import logging

from logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

import classifier_pb2
import classifier_pb2_grpc
import optimizer
import model


class ClassifierServicer(classifier_pb2_grpc.ClassifierServicer):
    """
    gRPC Classification Service Implementation.

    This class defines the optimized classification RPC method used for
    benchmark experiments. It overrides the method defined in the
    generated gRPC class `ClassifierServicer`.

    Responsibilities
    ----------------
    - receive a ClassificationRequest over gRPC
    - preprocess the review text using a Cython-compiled function
    - classify the cleaned text using a lightweight ML model
    - return customer_id, segment label, and confidence score

    Error handling:
    - Logs all exceptions during preprocessing or model inference
    - Returns safe fallback values ("unknown", 0.0) if failure occurs

    This ensures the gRPC server is robust during heavy load testing.
    """

    def Classify(
        self,
        request: classifier_pb2.ClassificationRequest,
        context: grpc.ServicerContext
    ) -> classifier_pb2.ClassificationResponse:
        """
        Process a classification request and return an optimized response.

        Parameters
        ----------
        request : ClassificationRequest
            The gRPC request message containing:
                - customer_id : string
                - review_text : string

        context : grpc.ServicerContext
            Provides RPC metadata, deadlines, and cancellation signals.
            Not used directly but required by gRPC framework.

        Returns
        -------
        ClassificationResponse
            Response containing:
                - customer_id : string
                - segment : string
                - confidence : float

        Notes
        -----
        - Preprocessing uses a Cython-accelerated function.
        - Model inference uses an in-memory lightweight model.
        - All errors are logged and never crash the server.
        """
        logger.info(f"Received gRPC request for customer: {request.customer_id}")

        # ------------------------------
        # 1. Preprocessing
        # ------------------------------
        try:
            cleaned_text = optimizer.clean_text(request.review_text)
        except Exception:
            logger.error("Text preprocessing failed", exc_info=True)
            cleaned_text = ""   # Safe fallback

        # ------------------------------
        # 2. ML Model Inference
        # ------------------------------
        try:
            segment, confidence = model.get_classification(cleaned_text)
        except Exception:
            logger.error("Model inference failed", exc_info=True)
            segment, confidence = "unknown", 0.0

        logger.info(f"Classified {request.customer_id}: {segment} ({confidence:.2f})")

        # ------------------------------
        # 3. Construct Response
        # ------------------------------
        return classifier_pb2.ClassificationResponse(
            customer_id=request.customer_id,
            segment=segment,
            confidence=confidence
        )


def serve() -> None:
    """
    Start the gRPC classification server.

    This function:
    - creates a gRPC server using a thread pool
    - registers the ClassifierServicer implementation
    - exposes the service on port 50051
    - blocks indefinitely until shutdown

    The server is fully compatible with Kubernetes and supports high
    concurrency via Python's ThreadPoolExecutor.

    Ports
    -----
    RPC endpoint: 0.0.0.0:50051

    Raises
    ------
    KeyboardInterrupt
        Gracefully stops the server on interruption.
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    classifier_pb2_grpc.add_ClassifierServicer_to_server(
        ClassifierServicer(),
        server
    )

    server.add_insecure_port('[::]:50051')
    logger.info("Starting optimized gRPC server on port 50051...")

    server.start()

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Stopping gRPC server...")
        server.stop(0)


if __name__ == '__main__':
    serve()