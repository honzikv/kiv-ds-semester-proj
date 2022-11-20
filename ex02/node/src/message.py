class Message:
    """
    Simple object that is send via sockets
    """

    def __init__(self, key: str, value, sender: int):
        """
        Constructor for the message - we use simple key-value pairs that are pickled and sent via sockets
        Args:
            key: key of the message
            value: value of the message
            sender: id of the sender
        """
        self.key = key
        self.value = value
        self.sender_id = sender

    def __str__(self) -> str:
        return f"Message(key={self.key}, value={self.value}, sender_id={self.sender_id})"
