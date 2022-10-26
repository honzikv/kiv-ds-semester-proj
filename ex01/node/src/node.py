import socket
import queue
import pickle
import time
import threading
from enum import Enum
from random import random
from message import Message


class NodeColor(Enum):
    """
    Node color / state
    """
    RED = 'red',
    GREEN = 'green',
    INIT = 'init'


MAX_MESSAGE_LEN = 4096  # 4K will suffice
MAX_ELECTION_TIME_SECS = 10  # 10 seconds
HEARTBEAT_TIMEOUT_SECS = 15  # 15 seconds
ELECTION_DIFFERENT_MSG_RECEIVED_SLEEP_INTERVAL_SECS = 1  # 1 second
COLOR_ASSIGNMENT_TIMEOUT_SECS = 20  # 20 seconds


class Node:
    """
    Node class contains all the logic for node communication which is done via sockets.
    """

    def __init__(self, node_addr, node_addrs: list):
        """
        Creates a new node with given hostname and (max) number of nodes in the network
        Args:
            node_addr: address of this node
            node_addrs: list of node addresses where id is the index in the list
        """
        self.addr = node_addr  # address of this node
        self.node_addrs = node_addrs
        self.id = self.node_addrs.index(self.addr)
        self.max_node_id = len(self.node_addrs) - 1

        self.color = NodeColor.INIT  # type: NodeColor
        self.master = False  # whether this node is master
        self.alive_nodes = set()  # set of all slave nodes in the cluster
        self.master_id = None  # id of the master node, if None then reconnection is necessary

        # Queue for messages received from other nodes
        self.received_messages = queue.Queue(maxsize=4096)
        self.listener_thread = None  # listens to messages and adds them to the queue
        self.uncolored_nodes = set()  # set of nodes that have not yet been colored
        self.node_colors = {}

    def change_color(self, to):
        """
        Changes the color of this node
        """
        self.color = to
        print(f'Changing color from {self.color} to {to}')

    def listener_thread_main(self):
        """
        Main function for the listener thread
        """

        print(f'Listening on addr: {self.addr}')
        while True:
            with socket.socket() as sock:
                data = sock.recv(MAX_MESSAGE_LEN)
                try:
                    # Unpickle the pickle 🥒
                    message = pickle.loads(data)
                    print(f'Received message: {message}')
                    self.received_messages.put(message)
                except TypeError:  # debug
                    print(f'Could not unpickle data: {data}')

    def send_message(self, node_id, key, value=None):
        """
        Sends message over UDP to node with given id
        """

        message = Message(key, value, self.addr)
        with socket.socket() as sock:
            sock.setblocking(False)
            sock.sendto(pickle.dumps(message), self.node_addrs[node_id])

    def run(self):
        """
        Starts the node
        """
        print(f'Starting node: {self.addr}')

        # Create new thread that will read messages from the socket and add them to the queue
        self.listener_thread = threading.Thread(target=self.listener_thread_main)
        self.listener_thread.start()
        self.node_main()

    def read_next_message_from_queue(self, timeout_secs=None) -> Message:
        """
        Reads next message from queue, returning either the read message or none if the timeout is reached
        Args:
            timeout_secs (int): timeout in seconds, None sets this to 0
        """

        try:
            return self.received_messages.get(block=True, timeout=timeout_secs)
        except queue.Empty:
            return None

    def broadcast_message(self, key, value=None):
        for node_id in range(self.node_addrs):
            self.send_message(id, key, value)

    def declare_self_as_master(self):
        """
        Declares this node as a master - sets state for master and sends a message to all other nodes
        """
        self.master = True
        self.color = NodeColor.GREEN
        print(f'This node ({self.addr}) is the master')
        self.broadcast_message('election', 'victory')

    def node_main(self):
        while True:
            if self.master_id is None:
                # If there is no master this means we are not in the cluster
                self.establish_master()

            if self.master:
                # Run master main fn
                self.master_main()
            else:
                # Run slave main fn
                self.slave_main()

    def establish_master(self):
        print('Establishing new master ...')

        # If node has the highest id we simply send a victory message to all other nodes and become the master
        if self.id == self.max_node_id:
            self.declare_self_as_master()
            return

        # Otherwise broadcast an election message to all other nodes with higher id
        for node_id in range(len(self.node_addrs)):
            self.send_message(node_id, 'election', self.id)

        # And begin reading messages until master is resolved
        self.master = False
        while True:  # Loop until master is not established, or we have waited for too long

            # Read next message from queue
            message = self.read_next_message_from_queue(MAX_ELECTION_TIME_SECS)
            if message is None:
                # If we receive no answer after sending election message we declare ourselves as master
                self.declare_self_as_master()
                return

            print(f'Received message: {message}')

            # Otherwise check if the message is an election message
            if message.key != 'election':
                time.sleep(ELECTION_DIFFERENT_MSG_RECEIVED_SLEEP_INTERVAL_SECS)
                continue

            if message.value == 'victory':
                # We have received a victory message from another node
                self.master_id = message.sender_id
                print(f'Master (id={self.master_id}) has been established...')
                break

            if message.value == 'surrender':
                # We have received surrender message from another node that has higher id
                print('Found node with higher id, surrendering...')
                continue

            if message.value < self.id:
                self.send_message(message.sender_id, 'election', 'surrender')

    def master_main(self):
        print('Coordinating distributed operation (coloring the nodes) ...')
        self.find_active_nodes()
        self.assign_colors()
        if self.colors_assigned():
            print('All nodes have been assigned a color')

    def find_active_nodes(self):
        """
        Broadcasts heartbeat request to all other nodes in the network and waits for the responses
        """

        # Clear list of alive nodes and send them a heartbeat request
        self.alive_nodes.clear()
        self.node_colors.clear()
        self.uncolored_nodes.clear()
        self.broadcast_message('heartbeat', 'request')

        while True:
            # Read the message queue and react to the messages
            message = self.read_next_message_from_queue(timeout_secs=HEARTBEAT_TIMEOUT_SECS)
            if message is None:
                break

            if message.key == 'heartbeat':
                if message.value == 'request':
                    self.send_message(message.sender_id, 'heartbeat', 'response')
                elif message.value == 'response':
                    self.alive_nodes.add(message.sender_id)

    def assign_colors(self):
        # Calculate number of nodes that should be green - 1/3 of all nodes including master
        n_green = len(self.alive_nodes) / 3
        n_red = len(self.alive_nodes) - n_green

        self.change_color(NodeColor.GREEN)
        n_green -= 1

        # Random permutation of nodes
        nodes = list(self.alive_nodes)
        random.shuffle(nodes)

        for idx, node in enumerate(nodes):
            if idx < n_green:
                self.send_message(node, 'color', NodeColor.GREEN)
                continue

            self.send_message(node, 'color', NodeColor.RED)

        self.uncolored_nodes = set(nodes)

    def colors_assigned(self):
        """
        Ensures that all nodes have a color assigned
        """
        while True:
            message = self.read_next_message_from_queue(timeout_secs=COLOR_ASSIGNMENT_TIMEOUT_SECS)
            if message is None:
                return False

            if message.key == 'color':
                self.node_colors[message.sender_id] = message.value
                self.uncolored_nodes.remove(message.sender_id)

            if len(self.uncolored_nodes) == 0:
                return True
