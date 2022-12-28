# In some cases we need to send requests in a way that they do not block
# main message loop which is impossible with asyncio without await
# Hence, we need a background thread to run these tasks which is
# implemented in this file

import threading
import logging_factory

from queue import Queue

__logger = logging_factory.create_logger('background_tasks')
__message_queue = Queue()
__terminate = False


def __run_tasks():
    """
    Runs task from the queue
    """
    while not __terminate:
        try:
            task = __message_queue.get()
            __logger.debug(f'Processing new task: {task}')
            task()
        except Exception as e:
            __logger.error(f'Failed to run task: {e}')


__thread = threading.Thread(target=__run_tasks)
__thread.start()


def terminate():
    """
    Terminates the background thread
    """
    global __terminate
    __terminate = True
    __thread.join()


def add_task(task: callable):
    """
    Adds task to the queue - task must be a callable without parameters

    Args:
        task (callable): task to be executed
    """
    __message_queue.put(task)
