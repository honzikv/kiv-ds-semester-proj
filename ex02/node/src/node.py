from enum import Enum
import os
import queue
import time
import math
import random
from typing import Union
from message import Message
from node_logger import NodeLogger
from messenger import Messenger


ELECTION_MSG_TIMEOUT_SECS = 10
ELECTION_UNSUCESSFUL_SLEEP_SECS = 7
HEARTBEAT_INTERVAL_SECS = 5
COLOR_ASSIGNMENT_SECS = 7
NODE_ALIVE_TIMEOUT_SECS = 15


class Node:
    """
    This class wraps a node's behavior and consumes messages from
    the message queue passed as a parameter
    """

    def __init__(self,
                 id: int,
                 node_addrs: list,
                 message_queue: queue.Queue,
                 log_file: os.path):
        """
        Used to create new node - one per process / machine

        Args:
            id (int): identifier of the node - in this case it is just 
                      an index to the node addrs array
            node_addrs (list): list of all nodes including "this" one
            log_file (os.path): path to the log file - this file will be 
                                erased and used for logging
        """

        self.node_addrs = node_addrs
        self.id = id
        self.max_node_id = len(node_addrs) - 1
        self.message_queue = message_queue

        self.color = 'init'  # init, red, green
        self.is_master = False  # Is this node the master?
        self.master_id = None  # id of the master
        self.surrendered = False

        # Structures to keep track of alive / colored nodes (used in master mode)
        self.alive_nodes = set()
        self.node_colors = {}
        self.uncolored_nodes = set()

        # Create logger and messenger helper objects
        self.logger = NodeLogger(id, log_file)
        self.messenger = Messenger(
            id=self.id,
            node_addrs=self.node_addrs,
        )

        # Structures to keep track of health of nodes
        self.last_master_response = None

    def change_color(self, to):
        """
        Changes color of the node to the given color.
        The result is logger to the console and output file
        Args:
            to (str): name of the new color
        """
        self.logger.log(f'Changing color from "{self.color}" to "{to}"')
        self.color = to

    def assign_color(self, id, color):
        """
        Assigns color to the given node - saved to "node_colors" dict
        and logged to console and output file

        Args:
            id (int): id of the node to assign color to
            color (str): name of the new color
        """
        self.node_colors[id] = color
        if id == self.id:
            self.change_color(color)
        else:
            self.logger.log(f'Node {id} was assigned color: "{color}"')

    def read_next_message(self, timeout_secs=None) -> Union[Message, None]:
        """
        Returns either the message or None if there is no message available
        within the given timeout. Method does not wait if timeout is set to None

        Args:
            timeout_secs (float, optional): Timeout in seconds
        """

        try:
            return self.message_queue.get(
                block=True, timeout=timeout_secs  # block is ignored if timeout is None
            )
        except queue.Empty:
            return None

    def run(self):
        """
        Main loop of the node
        """

        self.logger.log('Starting node')
        self.logger.log(f'Current color is "{self.color}"')

        while True:
            if self.master_id is None:
                self.logger.log('Master is unknown, trying to find it')
                self.election_mode()

                if self.master_id is None:
                    # If we still don't know the master, sleep for a while
                    time.sleep(ELECTION_UNSUCESSFUL_SLEEP_SECS)
                    continue

            if self.is_master:
                self.setup_colors()
                self.logger.log('Master setup complete')
                self.master_loop()
            else:
                self.slave_setup()
                if self.color == 'init':
                    self.logger.log('Slave setup failed')
                    self.master_id = None
                    time.sleep(ELECTION_UNSUCESSFUL_SLEEP_SECS)
                    continue

                self.logger.log('Slave setup complete')
                self.slave_loop()

    def election_mode(self):
        """
        Begins establishing master node in the network
        """

        self.logger.log('Attempting to establish new master')

        # Send election message to nodes with higher id
        # If some of them responds we know that we are not the master
        for node_id in range(self.id + 1, self.max_node_id):
            self.messenger.send_message(
                node_id=node_id,
                endpoint='election',
                value=self.id,
            )

        self.handle_election_messages()

    def handle_election_message(self, message: Message):
        """
        Handles single election message.

        Args:
            message (Message): election message

        Returns:
            str: to signal whether to exit the loop
        """

        if message.value == 'victory':
            # We have received a victory message from another node
            self.master_id = message.node_id
            self.is_master = False
            self.logger.log(
                f'Master (NODE-{self.master_id + 1}) has been established via victory message')
            return True

        if message.value == 'surrender':
            # We have received a surrender message from another node
            # This means that we won't be the master
            self.logger.log('Found node with higher id, surrendering...')
            self.surrendered = True

        if int(message.value) < self.id:
            self.log_message(
                'Found node with lower id, sending surrender message')
            self.messenger.send_message(
                node_id=message.node_id,
                endpoint='election',
                value='surrender',
            )

        return False

    def handle_election_messages(self):
        """
        Handles election messages from other nodes
        """

        self.surrendered = False  # flag to keep if we received a surrender message
        while True:
            message = self.read_next_message(
                timeout_secs=ELECTION_MSG_TIMEOUT_SECS)

            if message is None:
                if not self.surrendered:
                    self.declare_self_as_master()
                break

            if message.key != 'election':
                continue  # Ignore non-election messages

            election_finished = self.handle_election_message(message)
            if election_finished:
                break

    def declare_self_as_master(self):
        """
        Declares self as the master node, sending broadcast victory
        message to other nodes in the network
        """

        self.is_master = True
        self.master_id = self.id
        self.logger.log(f'Declaring self as master')
        self.messenger.broadcast('election', 'victory')

    def find_active_nodes(self):
        """
        Finds all active nodes in the network
        """

        self.alive_nodes.clear()
        # Send broadcast to all nodes with heartbeat request
        for node_id in range(self.max_node_id):
            if node_id == self.id:
                continue

            self.messenger.send_message(
                endpoint='heartbeat',
                node_id=node_id,
                value='request',
            )

        # Wait for the responses
        while True:
            if len(self.alive_nodes) == self.max_node_id + 1:
                break

            message = self.read_next_message(
                timeout_secs=HEARTBEAT_INTERVAL_SECS)
            if message is None or message.key != 'heartbeat':
                break

            # Node is alive when it responds or sends a request
            if message.value == 'request':
                self.messenger.send_message(
                    node_id=message.sender_id,
                    endpoint='heartbeat',
                    value='response',
                )
                self.alive_nodes.add(message.sender_id)
            elif message.value == 'response':
                self.alive_nodes.add(message.sender_id)

    def assign_colors(self):
        """
        Assigns colors to all nodes that are alive (in self.alive_nodes)
        """

        # 1/3 of the nodes are green, the rest is red
        n_green = math.floor(len(self.alive_nodes) / 3)
        n_green -= 1  # - 1 for the master node
        self.assign_color(self.id, 'green')

        # Create list of the nodes and permute it
        nodes = list(self.alive_nodes)
        random.shuffle(nodes)

        for idx, node_id in enumerate(nodes):
            self.messenger.send_message(
                node_id=node_id,
                endpoint='color',
                # First n_green nodes are green, the rest is red
                value='green' if idx < n_green else 'red',
            )

        # Uncolored nodes set is used to keep track of nodes that are yet
        # to respond
        self.uncolored_nodes = set(nodes)

    def all_colors_assigned(self):
        """
        Ensures that all nodes have assigned colors
        """

        while True:
            message = self.read_next_message(HEARTBEAT_INTERVAL_SECS)
            if message is None:
                break

            if message.key == 'color':
                self.uncolored_nodes.remove(message.sender_id)
                self.assign_color(message.sender_id, message.value)

            if message.key == 'heartbeat' and message.value == 'request':
                self.messenger.send_message(
                    node_id=message.sender_id,
                    endpoint='heartbeat',
                    value='response',
                )

        return len(self.uncolored_nodes) == 0

    def setup_colors(self):
        """
        Runs master setup - setups color for every alive node in the cluster
        """

        self.logger.log('Attempting to color the nodes')

        # Find active nodes
        self.find_active_nodes()

        # Color the nodes
        self.assign_colors()

        if (self.all_colors_assigned()):
            self.logger.log('All nodes have been colored')
        else:
            self.logger.log('Error, not all nodes have been colored')

        self.print_node_colors()

    def slave_setup(self):
        """
        Runs cluster setup for slave node
        """

        self.logger.log('Running setup for slave mode')
        self.change_color('slave')

        while True:
            message = self.read_next_message(COLOR_ASSIGNMENT_SECS)
            if message is None:
                break

            if message.key == 'color':
                self.change_color(message.value)
                self.messenger.send_message(
                    node_id=self.master_id,
                    endpoint='color',
                    value=self.color
                )
                break

            if message.key == 'heartbeat' and message.value == 'request':
                self.messenger.send_message(
                    node_id=self.master_id,
                    endpoint='heartbeat',
                    value='response',
                )

    def slave_loop(self):
        """
        Loop for slave mode.
        Here we react to incoming messages and send heartbeats to the master.
        If the master does not respond we initialize election
        """

        self.messenger.send_message(
            node_id=self.master_id,
            endpoint='heartbeat',
            value='request',
        )
        # We assume
        last_heartbeat_request = time.time()
        self.last_master_response = last_heartbeat_request

        while True:
            # If master did not respond until timeout start election
            # i.e. break out of the loop and set flags that will trigger it
            if time.time() - self.last_master_response > NODE_ALIVE_TIMEOUT_SECS:
                self.logger.log('Master did not respond, starting election')
                self.is_master = False
                self.master_id = None
                break

            # Send heartbeat request to master if timeout reached
            if time.time() - last_heartbeat_request > HEARTBEAT_INTERVAL_SECS:
                self.messenger.send_message(
                    node_id=self.master_id,
                    endpoint='heartbeat',
                    value='request',
                )

            message = self.read_next_message(HEARTBEAT_INTERVAL_SECS)
            if message is None:
                continue

            # If we get a heartbeat message we simply respond back
            if message.key == 'heartbeat':
                self.last_master_response = time.time()
                if message.value == 'request':
                    self.messenger.send_message(
                        node_id=message.sender_id,
                        endpoint='heartbeat',
                        value='response',
                    )

            # If we get an election message we handle it in a handle_election_message
            # This can be e.g. new node joining the cluster or new master having been
            # elected
            if message.key == 'election':
                # For slave we obviously only care for the master
                new_master = self.handle_election_message(message)
                if new_master:
                    return  # From here we will enter "slave_setup" again

            # Lastly we handle the color message
            if message.key == 'color':
                self.change_color(message.value)
                self.messenger.send_message(
                    node_id=self.master_id,
                    endpoint='color',
                    value=self.color
                )

    def handle_cluster_status(self, last_slave_responses):
        """
        Handles status of the cluster, returns True if cluster needs to be
        recolored - i.e. some node has died in the process

        Args:
            last_slave_responses (dict): dict

        Returns:
            bool: True if cluster needs to be recolored
        """

        # Begin checking if all slaves responded to the heartbeat
        now = time.time()
        for node_id, last_response in last_slave_responses.items():
            if now - last_response > NODE_ALIVE_TIMEOUT_SECS:
                self.logger.log(
                    f'Node {node_id} did not respond, recoloring...')
                return True

            if now - last_response > HEARTBEAT_INTERVAL_SECS:
                # Send heartbeat request to the slave if timeout reached
                self.messenger.send_message(
                    node_id=node_id,
                    endpoint='heartbeat',
                    value='request',
                )

        return False

    def master_loop(self):
        """
        Loop for master mode.
        """

        # Keep a dictioanary of responses from all slaves
        # At the start we assume that all slaves are alive
        last_slave_responses = {}

        for node_id in self.alive_nodes:
            self.messenger.send_message(
                node_id=node_id,
                endpoint='heartbeat',
                value='request',
            )
            last_slave_responses[node_id] = time.time()

        while True:
            message = self.read_next_message(HEARTBEAT_INTERVAL_SECS)
            if message is None:
                continue

            requires_recoloring = self.handle_cluster_status(
                last_slave_responses)
            if requires_recoloring:
                # Some node is unavailable - begin recoloring the nodes
                # I.e. exit this loop which will result in setup_colors being
                # run again
                return

            if message.key == 'heartbeat':
                last_slave_responses[message.sender_id] = time.time()
                if message.value == 'request':
                    self.messenger.send_message(
                        node_id=message.sender_id,
                        endpoint='heartbeat',
                        value='response',
                    )

            if message.key == 'election':
                new_master = self.handle_election_message(message)
                if new_master:
                    return  # return and we will start in the slave loop
