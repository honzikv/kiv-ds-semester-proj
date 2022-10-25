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
MAX_ELECTION_TIME = 10  # 10 seconds
HEARTBEAT_INTERVAL_S = 5  # 5 seconds


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
        self.listener_thread = None  # listens to messages and adds them to the queue
        self.sender_thread = None

    def listener_thread_main(self):
        # Start listening
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        print(f'Listening on port {self.communication_port}')
        while True:
            data = sock.recv(MAX_MESSAGE_LEN)
            try:
                # Unpickle the pickle 🥒
                message = pickle.loads(data)
                print(f'Received message: {message}')
                self.received_messages.put(message)
            except TypeError:  # debug
                print(f'Could not unpickle data: {data}')
                
    def broadcast_victory(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(Message(), ('255.255.255.255', self.communication_port))

            
                
    def send_msg(self, id, msg):
        """
        Sends message over UDP to node with given id
        """
        with socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(msg, (f'node-{id}', self.communication_port))

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

        self.establish_master()

    def establish_master(self):
        # - If P has the highest process ID, it sends a Victory message to all other processes and becomes the new Coordinator.
        # Otherwise, P broadcasts an Election message to all other processes with higher process IDs than itself.
        # - If P receives no Answer after sending an Election message, then it broadcasts a Victory message to all other processes
        # and becomes the Coordinator.
        # - If P receives an Answer from a process with a higher ID, it sends no further messages for this election
        # and waits for a Victory message. (If there is no Victory message after a period of time, it restarts 
        # the process at the beginning.)
        # - If P receives an Election message from another process with a lower ID it sends an Answer message 
        # back and if it has not already started an election, it starts the election process at the beginning, 
        # by sending an Election message to higher-numbered processes.
        # - If P receives a Coordinator message, it treats the sender as the coordinator.
        
        if self.id == self.id_limit:
            self.broadcast_victory()
        
        # Broadcast election message to all nodes with higher id
        for node_id in range(self.id + 1, self.id_limit):
            self.send_msg(node_id, Message('election', self.id))
            
        master_established = False
        while not master_established:
            message = self.received_messages.get(block=True, timeout=MAX_ELECTION_TIME)
            print(f'Got message: {message}')
            exit(0)

