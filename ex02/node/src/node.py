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
from timeout import Timeout
from exceptions import ElectionUnsuccessfulException, ClusterResetException, MasterDisconnectedException

# max time waiting for election queue message
ELECTION_MSG_QUEUE_SLEEP_SECS = 1
ELECTION_UNSUCESSFUL_SLEEP_SECS = 3  # sleep time for unsuccessful election
HEARTBEAT_INTERVAL_SECS = 5  # minimum time between heartbeats

# Timeouts
MAX_ELECTION_DURATION_SECS = 10
ELECTION_EXTENSION_SECS = 5
NODE_ALIVE_TIMEOUT_SECS = 10
# maximum time for all nodes to assign a color
MAX_COLOR_ASSIGNMENT_DURATION_SECS = 10


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
            n_color_tries (int): number of tries when coloring node before resetting alive nodes
        """
        self.node_addrs = node_addrs
        self.id = id
        self.max_node_id = len(node_addrs) - 1
        self.message_queue = message_queue

        self.color = 'init'  # init, red, green, slave, master
        self.is_master = False  # Is this node the master?
        self.master_id = None  # id of the master
        self.surrendered = False

        # Structures to keep track of alive / colored nodes (used in master mode)
        self.alive_nodes = {}  # all nodes that are alive
        self.node_colors = {}  # colors of all nodes
        self.nodes_to_color = {}  # remaining nodes that are yet to be colored
        self.nodes_alive_check_timeout = None

        # Create logger and messenger helper objects
        self.logger = NodeLogger(id, log_file)
        self.messenger = Messenger(
            id=self.id,
            node_addrs=self.node_addrs,
        )

        self.master_timeout = None  # last response from the master

    def change_color(self, color: str):
        """
        Changes color of the node to the given color.
        The result is logger to the console and output file
        Args:
            to (str): name of the new color
        """
        if self.color == color:
            return

        self.logger.log(f'Changing color from "{self.color}" to "{color}"')
        self.color = color

    def print_node_colors(self):
        for node_id in range(self.max_node_id + 1):
            if node_id in self.node_colors.keys():
                self.logger.log(
                    f'NODE-{node_id + 1} color: {self.node_colors[node_id]}')
            else:
                self.logger.log(
                    f'NODE-{node_id + 1} color: N/A (disconnected)')

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
        self.logger.log('Starting node! 💻')
        self.logger.log(f'Current color is "{self.color}"')

        while True:
            try:
                if self.master_id is None:
                    # If we don't have master we need to start an election
                    self.election()

            except ElectionUnsuccessfulException as err:
                self.logger.log(err)
                time.sleep(ELECTION_UNSUCESSFUL_SLEEP_SECS)
                continue

            if self.is_master:
                try:
                    self.master_loop()
                except ClusterResetException as err:
                    self.logger.log(err)
                    continue
            else:
                try:
                    self.slave_loop()
                except (MasterDisconnectedException, ClusterResetException) as err:
                    self.logger.log(err)
                    self.master_id = None
                    self.is_master = False

    def declare_self_as_master(self):
        """
        Declares self as the master node, sending broadcast victory
        message to other nodes in the network
        """
        self.is_master = True
        self.master_id = self.id
        self.logger.log(f'Declaring self as master')
        self.messenger.broadcast('election', 'victory')
        self.change_color('master')

    def election_victory_message(self, message: Message):
        """
        Checks whether message contains election victory message.
        Extracted to function for reusability

        Args:
            message (Message): message

        Returns:
            bool: True if message contains victory message, False otherwise
        """
        if message.value == 'victory':
            # If we receive victory message we set the data and terminate the election
            self.master_id = message.sender_id
            self.is_master = False
            self.logger.log(
                f'Master (NODE-{self.master_id + 1}) has been established via victory message...')
            return True
        return False

    def election_lower_id_message(self, message: Message):
        """
        Checks if election message is from node with lower id and sends surrender message if necessary

        Args:
            message (Message): _description_

        Returns:
            bool: True if message is from node with lower id, false otherwise
        """
        if isinstance(message.value, int) and message.value < self.id:
            # Someone with lower id contacted us -> send them surrender message
            self.logger.log(
                f'Found node with lower id (NODE-{message.value + 1}), sending surrender message...')
            self.messenger.send_message(
                node_id=message.sender_id, endpoint='election', value='surrender')

            return True
        return False

    def election(self):
        """
        Runs bully algorithm's election procedure
        """
        self.change_color('init')
        self.logger.log('Starting election! 🗳️')

        # Reset master state
        self.master_id, self.master, self.surrendered = None, False, False

        # Send election message to all nodes with higher id
        for node_id in range(self.id + 1, self.max_node_id + 1):
            self.messenger.send_message(
                node_id=node_id, endpoint='election', value=self.id)

        # Create election timeout - election ends after timeout is reached
        election_timeout = Timeout(MAX_ELECTION_DURATION_SECS)
        while not election_timeout.timed_out():
            message = self.read_next_message(ELECTION_MSG_QUEUE_SLEEP_SECS)
            if message is None or message.key != 'election':
                continue

            if self.election_victory_message(message):
                return

            if message.value == 'surrender' and not self.surrendered:
                # If we did not surrender yet we surrender and extend the timeout
                election_timeout.extend(ELECTION_EXTENSION_SECS)
                self.surrendered = True
                continue

            self.election_lower_id_message(message)

            if message.key == 'color' or message.key == 'heartbeat':
                self.logger.log(message)

        if not self.surrendered:
            # If we did not surrender send victory message
            self.declare_self_as_master()
        else:
            # Otherwise throw an exception which will trigger election restart
            raise ElectionUnsuccessfulException(
                f'Election unsuccessful, will attempt again in {ELECTION_UNSUCESSFUL_SLEEP_SECS} seconds...'
            )

    def check_for_cluster_changes(self, message: Message):
        """
        Checks whether message changes the cluster, if so throws ClusterResetException

        Args:
            message (Message): message

        Raises:
            ClusterResetException: raised when node needs to be reconfigured
        """
        if message.key != 'election':
            # Only election messages are relevant for cluster changes
            return

        if self.election_victory_message(message):
            raise ClusterResetException(
                'Cluster reset due to master change...')

        if self.election_lower_id_message(message):
            self.is_master = False
            self.master_id = None
            raise ClusterResetException('Cluster reset due to new node...')

    def find_active_nodes(self):
        """
        Finds all active nodes in the cluster
        """
        # Reset state
        self.alive_nodes.clear()

        # Send broadcast to all nodes with heartbeat
        self.messenger.broadcast('heartbeat', 'request')

        # Wait for the responses
        search_timeout = Timeout(NODE_ALIVE_TIMEOUT_SECS)
        while not search_timeout.timed_out():
            if len(self.alive_nodes) == len(self.node_addrs) - 1:
                # All nodes have responded
                break

            message = self.read_next_message(1)
            if message is None:
                continue

            self.check_for_cluster_changes(message)

            if message.key != 'heartbeat':
                self.logger.log(
                    'find_active_nodes: Received unexpected message: ' + str(message))
                continue

            if message.sender_id not in self.alive_nodes:
                self.alive_nodes[message.sender_id] = Timeout(
                    NODE_ALIVE_TIMEOUT_SECS)

            if message.value == 'request':
                self.messenger.send_message(
                    node_id=message.sender_id, endpoint='heartbeat', value='response')

    def create_color_assignments(self):
        """
        Assigns colors to all nodes that are alive (in self.alive_nodes)
        and saves them to self.nodes_to_color
        """
        # 1/3 of the nodes are green, the rest is red
        n_green = math.ceil((len(self.alive_nodes) + 1) / 3)
        n_green -= 1  # - 1 for the master node
        self.change_color('green')
        self.node_colors[self.id] = 'green'

        # Create list of the nodes and permute it
        nodes = list(self.alive_nodes)
        random.shuffle(nodes)

        for idx, node_id in enumerate(nodes):
            self.nodes_to_color[node_id] = 'green' if idx < n_green else 'red'

    def all_colors_assigned(self):
        """
        Ensures that all nodes have assigned colors
        """
        # Send colors to alive nodes
        for node_id, color in self.nodes_to_color.items():
            self.messenger.send_message(
                node_id=node_id, endpoint='color', value=color)

        color_assignment_timeout = Timeout(MAX_COLOR_ASSIGNMENT_DURATION_SECS)
        while not color_assignment_timeout.timed_out():
            if len(self.nodes_to_color) == 0:
                break

            message = self.read_next_message(1)
            if message is None:
                continue

            self.check_for_cluster_changes(message)

            if message.sender_id not in self.alive_nodes:
                continue

            if message.key == 'color':
                del self.nodes_to_color[message.sender_id]
                self.node_colors[message.sender_id] = message.value
                continue

            # We also need to respond to heartbeats
            if message.key == 'heartbeat' and message.value == 'request':
                self.messenger.send_message(
                    node_id=message.sender_id, endpoint='heartbeat', value='response')

        return len(self.nodes_to_color) == 0

    def setup_colors(self, find_active_nodes=True):
        """
        Setups colors for each node in the cluster
        """
        self.logger.log('Setting up node colors...')
        if find_active_nodes:
            self.find_active_nodes()

        self.node_colors.clear()
        self.nodes_to_color.clear()
        self.create_color_assignments()
        if not self.all_colors_assigned():
            raise ClusterResetException(
                'Not all colors assigned, resetting cluster...')

        self.logger.log('Node colors have been set up!')
        self.print_node_colors()
        self.reset_timeouts()  # Reset timeouts for nodes

    def check_for_dead_nodes(self):
        """
        Checks whether all nodes are alive
        If not recolors the cluster accordingly
        """
        if not self.nodes_alive_check_timeout.timed_out():
            return

        dead_nodes = []
        for node_id, timeout in self.alive_nodes.items():
            if timeout.timed_out():
                dead_nodes.append(node_id)

        if len(dead_nodes) == 0:
            return

        self.logger.log(
            f'Detected dead nodes, dead nodes: {", ".join([f"NODE-{node_id+1}" for node_id in dead_nodes])}')
        for node_id in dead_nodes:
            del self.alive_nodes[node_id]

        self.setup_colors(find_active_nodes=False)

    def reset_timeouts(self):
        for timeout in self.alive_nodes.values():
            timeout.reset()

    def master_loop(self):
        """
        Runs node in master mode
        """
        self.change_color('master')
        self.setup_colors()

        # Timeout to check if all slaves are alive
        self.nodes_alive_check_timeout = Timeout(NODE_ALIVE_TIMEOUT_SECS / 2)

        while True:
            self.check_for_dead_nodes()

            message = self.read_next_message(1)
            if message is None:
                continue

            self.check_for_cluster_changes(message)

            # Slaves must send heartbeat request to master
            if message.key != 'heartbeat':
                continue

            if message.sender_id not in self.alive_nodes:
                self.alive_nodes[message.sender_id] = Timeout(
                    NODE_ALIVE_TIMEOUT_SECS)
                self.setup_colors(find_active_nodes=False)
                continue

            self.alive_nodes[message.sender_id].reset()  # reset the timer
            self.logger.log(
                f'Received heartbeat from NODE-{message.sender_id + 1}')
            self.messenger.send_message(
                node_id=message.sender_id, endpoint='heartbeat', value='response')

    def slave_loop(self):
        """
        Runs node in slave mode
        
        Raises:
            MasterDisconnectedException: raised if master is disconnected
        """
        self.change_color('slave')
        self.messenger.send_message(
            node_id=self.master_id, endpoint='heartbeat', value='request')

        heartbeat_timeout = Timeout(HEARTBEAT_INTERVAL_SECS)
        self.master_timeout = Timeout(NODE_ALIVE_TIMEOUT_SECS)

        while not self.master_timeout.timed_out():
            if heartbeat_timeout.timed_out():
                self.messenger.send_message(
                    node_id=self.master_id, endpoint='heartbeat', value='request')
                heartbeat_timeout.reset()

            message = self.read_next_message(1)
            if message is None:
                continue

            # self.logger.log(f'Received message: {message}')

            if self.check_for_cluster_changes(message):
                return

            if message.sender_id == self.master_id:
                # self.logger.log('Resetting master timeout')
                self.master_timeout.reset()

            # If we get a heartbeat message we simply respond back
            if message.key == 'heartbeat':
                if message.value == 'request':
                    self.messenger.send_message(
                        node_id=message.sender_id, endpoint='heartbeat', value='response')
                else:
                    self.logger.log(
                        f'Received heartbeat response from master (NODE-{self.master_id + 1})')

            # If we get a color change message we change our color
            if message.key == 'color':
                self.change_color(message.value)
                self.messenger.send_message(
                    node_id=self.master_id, endpoint='color', value=self.color)

        # Throw master disconnected exception
        raise MasterDisconnectedException(
            f'Master (NODE-{self.master_id + 1}) did not respond, starting an election')
