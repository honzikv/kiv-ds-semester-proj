import socket
import queue
import pickle
import threading
from enum import Enum


class NodeColor(Enum):
    """
    Node color / state
    """
    RED, GREEN, INIT = range(2)


MAX_MESSAGE_LEN = 4096  # 4K will suffice
HEARTBEAT_INTERVAL_MS = 5000  # 5 seconds


class Message:
    """
    Simple object that is send via sockets
    """

    def __init__(self, key, value):
        self.key = key
        self.value = value

    def __str__(self) -> str:
        return f"Message(key={self.key}, value={self.value})"


class Node:
    """
    Node class contains all logic for node communication which is done via UDP sockets.

    Each Node always creates two extra threads for listening and sending messages
    """

    def __init__(self, hostname: str, id_limit, communication_port=1337):
        self.hostname = hostname
        self.id_limit = id_limit
        self.communication_port = communication_port
        self.id = int(hostname.split('-')[1])
        self.state = None
        self.master = False
        self.nodes = []  # list of other known nodes

        # Queue for messages received from other nodes
        self.received_messages = queue.Queue(maxsize=4096)
        self.send_messages = queue.Queue(maxsize=4096)
        self.listener_thread = None  # listens to messages and adds them to the queue
        self.sender_thread = None

    def listener_thread_main(self):
        # Start listening
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        while True:
            data = sock.recv(MAX_MESSAGE_LEN)
            try:
                # Unpickle the pickle 🥒
                message = pickle.loads(data)
                print(f'Received message: {message}')
                self.received_messages.put(message)
            except TypeError:  # debug
                print(f'Could not unpickle data: {data}')

    def start(self):
        """
        Called when node is started - initializes threads for listening and sending messages
        """
        print(f'Starting node: {self.hostname}')
        self.state = NodeColor.INIT

        # Create listener thread and start it
        self.listener_thread = threading.Thread(
            target=self.listener_thread_main
        )
        self.listener_thread.start()
