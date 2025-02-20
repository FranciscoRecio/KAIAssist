import logging
import sys
from src.config.settings import Settings

settings = Settings()

def setup_logger(name: str) -> logging.Logger:
    """Set up a logger with the given name"""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
        
        # Format
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        
        # File handler for errors
        error_handler = logging.FileHandler('error.log')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        
        logger.addHandler(error_handler)
    
    return logger 