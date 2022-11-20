from concurrent.futures import ThreadPoolExecutor
import requests

DEFAULT_TIMEOUT_SECS = 3


class Messenger:
    """
    Serves as a wrapper for communication between nodes
    This could theoretically implement other communication protocols
    such as TCP, UDP, websockets, etc.
    """

    def __init__(self, id: int, node_addrs: list, timeout=DEFAULT_TIMEOUT_SECS) -> None:
        """
        Default constructor

        Args:
            id (int): id of the node
            node_addrs (list): list of all node addresses
            timeout (_type_, optional): Request timeout. Defaults to DEFAULT_TIMEOUT_SECS.
        """
        self.id = id
        self.node_addrs = node_addrs
        self.timeout = timeout

        # To send requests async we create a thread pool executor which performs requests.post
        # for every message sent
        self.thread_pool_executor = ThreadPoolExecutor(max_workers=5)

    def send_message_sync(self, node_id: int, endpoint: str, value):
        try:
            return requests.post(
                url=f'{self.node_addrs[node_id]}/{endpoint}',
                json={
                    'value': value,
                    'sender_id': self.id
                },
                timeout=self.timeout
            )
        except Exception as e:
            # print(e, flush=True)
            pass

    def send_message(self, node_id: int, endpoint: str, value):
        """
        Sends message to given node address

        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        # Result is actually not relevant for us, we just don't want to block the caller thread
        self.thread_pool_executor.submit(
            self.send_message_sync, node_id, endpoint, value)

    def broadcast(self, endpoint: str, value):
        """
        Broadcasts message to all nodes

        Args:
            endpoint (str): endpoint to send the message to
            value (any): value to send, must be JSON serializable i.e.
                            int, float, str, bool, list, dict, None
        """
        for node_id in range(len(self.node_addrs)):
            if node_id != self.id:
                self.send_message(
                    node_id=node_id,
                    endpoint=endpoint,
                    value=value
                )
