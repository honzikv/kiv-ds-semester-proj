import requests

DEFAULT_TIMEOUT_SECS = 5


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

    def send_message(self, node_id, endpoint: str, value):
        """
        Sends message to given node address

        Returns:
            bool: True if message was sent successfully, False otherwise
        """

        node_addr = self.node_addrs[node_id]
        try:
            requests.post(
                url=f'{node_addr}/{endpoint}',
                json={
                    'value': value,
                    'sender_id': self.id
                },
                timeout=self.timeout
            )
            return True
        except Exception as ex:
            # print(f'Error sending message to {node_addr}: {ex}')
            return False

    def broadcast(self, endpoint, value):
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
