import logging
import queue
import random
import sys

import requests

from message import Message

ELECTION_TIMEOUT = 30
HEARTBEAT_TIMEOUT_SECS = 10
COLOR_ASSIGNMENT_TIMEOUT_SECS = 60  # 20 seconds
received_messages = queue.Queue(maxsize=4096)

_logger = logging.getLogger(__name__)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
_logger.addHandler(console_handler)


# print = _logger.info


def read_next_message_from_queue(timeout_secs=None) -> Message | None:
    """
    Reads next message from queue, returning either the read message or none if the timeout is reached. If timeout is
    None this function is nonblocking, otherwise it blocks until a message is received or the timeout is reached.
    Args:
        timeout_secs (int): timeout in seconds, None sets this to 0
    """

    try:
        return received_messages.get(block=True, timeout=timeout_secs)
    except queue.Empty:
        return None


class Node:

    def __init__(self, node_addrs, node_addr) -> None:
        self.node_addrs = node_addrs
        self.addr = node_addr

        # Node addresses are simple URLs that are passed to each node
        # sorted alphabetically so we can easily derive node id
        # as index in the node_addrs array
        self.id = self.node_addrs.index(self.addr)
        self.max_node_id = len(self.node_addrs) - 1
        self.color = 'init'
        self.master = False
        self.master_id = None
        self.alive_nodes = set()
        self.node_colors = {}
        self.uncolored_nodes = set()

    def change_color(self, to):
        print(f'NODE {self.addr} Changing color from {self.color} to {to}')
        self.color = to

    def send_message(self, node_addr: str, endpoint: str, value):
        try:
            requests.post(f'{node_addr}/{endpoint}',
                          json={'value': value, 'sender_id': self.id},
                          timeout=HEARTBEAT_TIMEOUT_SECS)
        except Exception as ex:
            print(ex)

    def broadcast(self, endpoint, value):
        """
        Broadcasts a message to all nodes
        """
        for node_id in range(self.max_node_id):
            if node_id == self.id:
                continue

            self.send_message(
                endpoint=endpoint,
                node_addr=self.node_addrs[node_id],
                value=value,
            )

    def declare_self_as_master(self):
        self.master = True
        self.master_id = self.id
        print(f'This node {self.addr} is the master now')
        self.broadcast('election', 'victory')

    def run(self):
        """
        Starts the node
        """

        while True:
            if self.master_id is None:
                self.establish_master_conn()
                continue

            if self.master:
                self.master_loop()
                continue

            self.slave_loop()

    def establish_master_conn(self):
        """
        Begins to establish master in the network.
        """
        print('Attempting to establish new master')
        # If we are the highest id in the cluster we must be the master
        # So just broadcast to all other nodes to surrender
        if self.id == self.max_node_id:
            self.declare_self_as_master()
        else:
            # Else send election message to all other nodes
            for node_id in range(self.id + 1, self.max_node_id):
                self.send_message(
                    endpoint='election',
                    node_addr=self.node_addrs[node_id],
                    value=self.id,
                )

        self.wait_for_election_results()

    def wait_for_election_results(self):
        """
        Waits for election results, this must be called even in node that knows they are the master
        """

        while True:
            message = read_next_message_from_queue(timeout_secs=ELECTION_TIMEOUT)
            if message is None:
                self.declare_self_as_master()
                break

            if message.key != 'election':
                # received_messages.put(message)  # Add message back to queue
                continue

            if message.value == 'victory':
                # We have received a victory message from another node
                self.master_id = message.sender_id
                print(f'Master (id={self.master_id}) has been established via victory message')
                break

            if message.value == 'surrender':
                # We have received surrender message from another node that has higher id
                print('Found node with higher id, surrendering...')
                continue

            if int(message.value) < self.id:
                print('Found node with lower id, sending surrender order.')
                self.send_message(
                    node_addr=self.node_addrs[message.sender_id],
                    endpoint='election',
                    value='surrender',
                )

    def master_loop(self):
        print('Coordinating distributed operation (coloring the nodes) ...')
        self.find_active_nodes()
        self.assign_colors()
        if self.colors_assigned():
            print('All nodes have been assigned a color')
            print(self.node_colors)

        while True:
            message = read_next_message_from_queue(timeout_secs=HEARTBEAT_TIMEOUT_SECS)
            if message is None:
                print('Slaves are all dead, dying...')
                exit(4)

            if message.key != 'heartbeat':
                continue

            if message.value == 'request':
                self.send_message(
                    node_addr=self.node_addrs[message.sender_id],
                    endpoint='heartbeat',
                    value='response',
                )

    def find_active_nodes(self):
        print('Finding active nodes...')
        self.alive_nodes.clear()
        self.node_colors.clear()
        self.uncolored_nodes.clear()

        for node_id in range(self.max_node_id):
            if node_id == self.id:
                continue

        self.broadcast('heartbeat', 'request')

        while True:
            if len(self.alive_nodes) == self.max_node_id + 1:
                break

            message = read_next_message_from_queue(timeout_secs=HEARTBEAT_TIMEOUT_SECS)
            if message is None:
                break

            if message.key == 'heartbeat':
                if message.value == 'request':
                    self.send_message(self.node_addrs[message.sender_id], 'heartbeat', 'response')
                elif message.value == 'response':
                    self.alive_nodes.add(message.sender_id)

    def assign_colors(self):
        n_green = len(self.alive_nodes) - 1
        n_green -= 1

        # Change color for this node since its the master
        self.change_color('green')
        self.node_colors[self.id] = 'green'

        # Random permutation of nodes
        nodes = list(self.alive_nodes)
        random.shuffle(nodes)

        for idx, node_id in enumerate(nodes):
            if idx < n_green:  # assign green color
                self.send_message(self.node_addrs[node_id], 'color', 'green')
                continue

            # The rest is colored red
            self.send_message(self.node_addrs[node_id], 'color', 'red')

        # This set is used to keep track of nodes that have not yet responded
        self.uncolored_nodes = set(nodes)

    def colors_assigned(self):
        """
        Ensures that all nodes have a color assigned
        """

        while True:
            if len(self.uncolored_nodes) == 0:
                return True

            message = read_next_message_from_queue(timeout_secs=HEARTBEAT_TIMEOUT_SECS)
            if message is None:
                return False

            if message.key == 'color':
                self.node_colors[message.sender_id] = message.value
                self.uncolored_nodes.remove(message.sender_id)

    def slave_loop(self):
        print('Entering slave mode ...')

        while True:
            message = read_next_message_from_queue(timeout_secs=COLOR_ASSIGNMENT_TIMEOUT_SECS)
            if message is None:
                self.master_id = None
                return

            if message.key == 'color':
                self.change_color(message.value)
                self.send_message(
                    node_addr=self.node_addrs[self.master_id],
                    endpoint='color',
                    value=self.color,
                )
                break

            if message.key == 'heartbeat' and message.value == 'request':
                self.send_message(
                    node_addr=self.node_addrs[message.sender_id],
                    endpoint='heartbeat',
                    value='response',
                )

        # Sent heartbeats to the master
        while True:
            message = read_next_message_from_queue(timeout_secs=HEARTBEAT_TIMEOUT_SECS)
            if message is None:
                print('No heartbeat from master, dying...')
                exit(4)

            if message.key == 'heartbeat' and message.value == 'request':
                self.send_message(
                    node_addr=self.node_addrs[message.sender_id],
                    endpoint='heartbeat',
                    value='response',
                )
