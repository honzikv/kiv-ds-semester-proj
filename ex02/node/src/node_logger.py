import os
import time


class NodeLogger:
    """
    Class used to log into node's console and log file
    """

    def __init__(self, id: int, log_file: os.path):
        """
        Creates new logger

        Args:
            id (int): node's id
            log_file (os.path): path to the log file
        """
        self.id = id
        self.log_file = log_file
        open(self.log_file, 'w').close()  # clear log file

    def log(self, message):
        """
        Logs given message to the stdout and to the log file

        Args:
            message (str): message to log
        """
        localtime = time.localtime()
        current_time = time.strftime('%H:%M:%S', localtime)
        msg = f'[{current_time}] (NODE-{self.id + 1}): {message}'
        print(msg, flush=True)  # flush is needed otherwise
        # it does not show in the terminal right away

        # Write to file
        with open(self.log_file, 'a', encoding='utf-8') as file:
            file.write(msg + '\n')
