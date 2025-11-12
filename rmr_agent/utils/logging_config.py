import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# Define log directory
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")

# Create log directory if it doesn't exist
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Define log file path
LOG_FILE = os.path.join(LOG_DIR, "rmr_agent.log")

# Define formatting
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
CONSOLE_FORMAT = "%(levelname)s - %(message)s"

# Define log levels
DEFAULT_LEVEL = logging.INFO


def setup_logger(name, log_file=LOG_FILE, level=DEFAULT_LEVEL, console_output=True,
                file_output=True, max_file_size=10*1024*1024, backup_count=5):
    """
    Set up a logger with file and/or console output.

    Args:
        name: Name of the logger, typically __name__
        log_file: Path to the log file
        level: Logging level (default: INFO)
        console_output: Whether to output logs to console
        file_output: Whether to output logs to file
        max_file_size: Maximum log file size in bytes (default: 10MB)
        backup_count: Number of backup files to keep (default: 5)

    Returns:
        Logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    # Create formatters
    file_formatter = logging.Formatter(DEFAULT_FORMAT)
    console_formatter = logging.Formatter(CONSOLE_FORMAT)

    # Add file handler if requested
    if file_output:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        # Create rotating file handler
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_file_size,
            backupCount=backup_count
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    # Add console handler if requested
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger


# Configure the root logger
def configure_root_logger(level=DEFAULT_LEVEL):
    """Configure the root logger with sensible defaults"""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT))
    root_logger.addHandler(console_handler)

    # Add file handler
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10*1024*1024,
        backupCount=5
    )
    file_handler.setFormatter(logging.Formatter(DEFAULT_FORMAT))
    root_logger.addHandler(file_handler)

    return root_logger


# Create a default logger instance for quick imports
def get_default_logger():
    """Get a default logger for quick imports"""
    return setup_logger("rmr_agent")


# Default logger instance
default_logger = get_default_logger()


if __name__ == "__main__":
    # Test the logger
    logger = setup_logger(__name__)
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")