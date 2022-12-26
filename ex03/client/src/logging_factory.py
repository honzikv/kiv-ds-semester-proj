import logging
import os

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

root_dir = '/vagrant/'
os.makedirs(root_dir, exist_ok=True)

DEFAULT_LOG_FILE = os.path.join(root_dir, 'log.log')


def create_logger(name: str, logfile: str | None = DEFAULT_LOG_FILE, loglevel=logging.DEBUG):
    """
    Creates a new logger with the given name and loglevel.

    Args:
        name (str): name of the module / logger
        logfile (str | None, optional): specifies the logfile to use. Defaults to None.
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
