import logging
import os
from datetime import datetime


def get_logger(name="auto_test"):
    """
    Get a logger instance (singleton pattern)
    :param name:
    :return:
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Prevent duplicate handlers (singleton guard)
    if logger.handlers:
        return logger

    # Console output
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # File output
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)  # auto-create logs/ dir

    log_file = os.path.join(
        log_dir,
        "{}.log".format(datetime.now().strftime("%Y-%m-%d")),
    )
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    # Unified format
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # Bind to logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
