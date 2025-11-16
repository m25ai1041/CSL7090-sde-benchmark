import grpc
from concurrent import futures
import time
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
    This is the "Final" gRPC service.
    """
    
    def Classify(self, 
                 request: classifier_pb2.ClassificationRequest, 
                 context: grpc.Context) -> classifier_pb2.ClassificationResponse:
        """
        This is the "Optimized" method.
        
        Input:  classifier_pb2.ClassificationRequest (gRPC message)
                grpc.Context (gRPC context)
        Output: classifier_pb2.ClassificationResponse (gRPC message)
        """
        logger.info(f"Received gRPC request for customer: {request.customer_id}")
        
        # 1. Use the CYTHON-COMPILED preprocessor
        cleaned_text = optimizer.clean_text(request.review_text)
        
        # 2. Run the ML model
        segment, confidence = model.get_classification(cleaned_text)
        
        logger.info(f"Successfully classified customer: {request.customer_id}")
        return classifier_pb2.ClassificationResponse(
            customer_id=request.customer_id,
            segment=segment,
            confidence=confidence
        )

def serve() -> None:
    """
    Starts the gRPC server.
    
    Input:  None
    Output: None
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    classifier_pb2_grpc.add_ClassifierServicer_to_server(
        ClassifierServicer(), server
    )
    server.add_insecure_port('[::]:50051')
    logger.info("Starting 'Final' gRPC server on port 50051...")
    server.start()
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Stopping gRPC server...")
        server.stop(0)

if __name__ == '__main__':
    serve()