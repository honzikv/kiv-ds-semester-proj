import queue
import random
import time

import requests
from node_color import NodeColor

from message import Message

REQ_TIMEOUT = 30
HEARTBEAT_TIMEOUT_SECS = 10
COLOR_ASSIGNMENT_TIMEOUT_SECS = 20  # 20 seconds
received_messages = queue.Queue(maxsize=4096)


def read_next_message_from_queue(timeout_secs=None) -> Message | None:
    """
    Reads next message from queue, returning either the read message or none if the timeout is reached
    Args:
        timeout_secs (int): timeout in seconds, None sets this to 0
    """

    try:
        return received_messages.get(block=True, timeout=timeout_secs)
    except queue.Empty:
        return None


class Node:

    def __init__(self, node_addrs, node_addr) -> None:
        global a
        self.node_addrs = node_addrs
        self.addr = node_addr

        # Node addresses are simple URLS and are passed to each node
        # sorted alphabetically so we can easily derive any node id
        # as index in the node_addrs array
        self.id = self.node_addrs.index(self.addr)
        self.max_node_id = len(self.node_addrs) - 1

        self.color = NodeColor.INIT
        self.master = False
        self.master_id = None
        self.alive_nodes = set()
        self.node_colors = {}
        self.uncolored_nodes = set()

    def change_color(self, to):
        self.color = to
        print(f'Changing color from {self.color} to {to}')

    def send_message(self, node_addr: str, endpoint: str, value):
        print('Sending message to node: ', node_addr)
        try:
            requests.post(f'{node_addr}/{endpoint}',
                          json={'value': value, 'sender_id': self.id},
                          timeout=REQ_TIMEOUT)
        except Exception as ex:
            print(ex)

    def declare_self_as_master(self):
        self.master = True
        self.master_id = self.id
        print(f'This node {self.addr} is the master now')
        for node_id in range(self.max_node_id):
            if node_id != self.id:
                self.send_message(
                    endpoint='election',
                    node_addr=self.node_addrs[node_id],
                    value='victory'
                )

    def run(self):
        """
        Starts the node
        """

        print(f'Starting node: {self.addr}')
        while True:
            if self.master_id is None:
                self.establish_master_conn()
                continue

            if self.master:
                self.master_loop()
                continue

            self.slave_loop()

    def establish_master_conn(self):
        print('Attempting to establish new master')
        # If we are the highest id in the cluster we must be the master
        # So just broadcast to all other nodes to surrender
        if self.id == self.max_node_id:
            print('This node is the highest id, declaring self as master')
            self.declare_self_as_master()
            return
        # Else send election message to all other nodes
        for node_id in range(self.max_node_id):
            if node_id == self.id:
                continue

            print('Sending election message to node: ', node_id)
            node_addr = self.node_addrs[node_id]
            self.send_message(
                endpoint='election',
                node_addr=node_addr,
                value=self.id
            )

        self.wait_for_election_results()

    def wait_for_election_results(self):
        # Begin listening for responses
        print('Waiting for election results')
        while True:
            message = read_next_message_from_queue(timeout_secs=REQ_TIMEOUT)
            if message is None:
                print('No election results received, declaring self as master')
                self.declare_self_as_master()
                break

            if message.key != 'election':
                print('Received non-election message, ignoring')
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

            if int(message.value) < self.id:
                print('Found node with lower id, sending surrender order.')
                self.send_message(
                    node_addr=self.node_addrs[message.sender_id],
                    endpoint='election',
                    value='surrender'
                )

    def master_loop(self):
        print('Coordinating distributed operation (coloring the nodes) ...')
        self.find_active_nodes()
        self.assign_colors()
        if self.colors_assigned():
            print('All nodes have been assigned a color')

    def find_active_nodes(self):
        self.alive_nodes.clear()
        self.node_colors.clear()
        self.uncolored_nodes.clear()

        while True:
            message = read_next_message_from_queue(timeout_secs=HEARTBEAT_TIMEOUT_SECS)
            if message is None:
                break

            if message.key == 'heartbeat':
                if message.value == 'request':
                    self.send_message(message.sender_id, 'heartbeat', 'response')
                elif message.value == 'response':
                    self.alive_nodes.add(message.sender_id)

    def assign_colors(self):
        n_green = len(self.alive_nodes) - 1
        self.change_color(NodeColor.GREEN)
        n_green -= 1

        # Random permutation of nodes
        nodes = list(self.alive_nodes)
        random.shuffle(nodes)

        for idx, node in enumerate(nodes):
            if idx < n_green:
                self.send_message(node, 'color', NodeColor.GREEN)
                continue

            # The rest is colored red
            self.send_message(node, 'color', NodeColor.RED)

        # This set is used to keep track of nodes that have not yet responded
        self.uncolored_nodes = set(nodes)

    def colors_assigned(self):
        """
        Ensures that all nodes have a color assigned
        """

        while True:
            message = read_next_message_from_queue(timeout_secs=HEARTBEAT_TIMEOUT_SECS)
            if message is None:
                return False

            if message.key == 'color':
                self.node_colors[message.sender_id] = message.value
                self.uncolored_nodes.remove(message.sender_id)

            if len(self.uncolored_nodes) == 0:
                return True

    def slave_loop(self):
        print('Waiting for master to assign colors ...')

        while True:
            message = read_next_message_from_queue(timeout_secs=COLOR_ASSIGNMENT_TIMEOUT_SECS)
            if message is None:
                self.master_id = None
                return

            if message.key == 'color':
                self.change_color(message.value)
                self.send_message(self.master_id, 'color', self.color)
                break

            if message.key == 'heartbeat' and message.value == 'request':
                self.send_message(message.sender_id, 'heartbeat', 'response')
