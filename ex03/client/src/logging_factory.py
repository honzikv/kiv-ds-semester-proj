import logging
import os
from env import NODE_NAME
from typing import Optional

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Create log directory and log file
root_dir = '/vagrant/'
os.makedirs(root_dir, exist_ok=True)
DEFAULT_LOG_FILE = os.path.join(root_dir, f'{NODE_NAME}.log')
with open(DEFAULT_LOG_FILE, 'w') as f:
    f.write('')


def create_logger(name: str, logfile: Optional[str] = DEFAULT_LOG_FILE, loglevel=logging.DEBUG):
    """
    Creates a new logger with the given name and loglevel.

    Args:
        name (str): name of the module / logger
        logfile (str, optional): path to the log file. Defaults to DEFAULT_LOG_FILE.
        loglevel (logging level, optional): _description_. Defaults to logging.DEBUG.

    Returns:
        Logger: configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(loglevel)

    if logfile:
        file_handler = logging.FileHandler(logfile)
        file_handler.setLevel(loglevel)
        logger.addHandler(file_handler)

    return logger
