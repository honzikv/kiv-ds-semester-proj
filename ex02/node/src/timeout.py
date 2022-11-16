import time
from typing import Union


class Timeout:
    """
    Simple time wrapper for measuring timeouts
    """

    def __init__(self, secs: Union[float, int]) -> None:
        """
        Creating new timeout will start measuring time right away
        Args:
            secs (Union[float, int]): timeout length in seconds
        """

        self.secs = secs
        self.start = time.time()

    def timed_out(self):
        """
        Returns True if the timer has timed out, False otherwise

        Returns:
            bool: True if timed out, False otherwise
        """

        return time.time() - self.start > self.secs

    def extend(self, additional: Union[float, int]):
        """
        Extends the timeout by given amount of seconds.
        This does not reset the timer, it just adds the given amount of seconds to the timeout
        Args:
            additional (Union[float, int]): additional amount of seconds to add to the timeout
        """

        self.secs += additional

    def reset(self):
        """
        Resets the timeout. 
        Note that extended timeouts will not reset to the original timeout value
        """

        self.start = time.time()
