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
from exceptions import ElectionUnsuccessfulException, ClusterResetException

# max time waiting for election queue message
ELECTION_MSG_QUEUE_SLEEP_SECS = 2
ELECTION_UNSUCESSFUL_SLEEP_SECS = 3  # sleep time for unsuccessful election
HEARTBEAT_INTERVAL_SECS = 5  # minimum time between heartbeats

# Timeouts
MAX_ELECTION_DURATION_SECS = 15
ELECTION_EXTENSION_SECS = 10
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
                 log_file: os.path,
                 n_color_tries=3):
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
        self.alive_nodes = set()  # all nodes that are alive
        self.node_colors = {}  # colors of all nodes
        self.nodes_to_color = {}  # remaining nodes that are yet to be colored
        self.n_color_tries = n_color_tries

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
                    self.election()

            except ElectionUnsuccessfulException as err:
                self.logger.log(err)
                time.sleep(ELECTION_UNSUCESSFUL_SLEEP_SECS)
                continue

            if self.is_master:
                try:
                    self.setup_colors()
                    self.master_loop()
                except ClusterResetException as err:
                    self.logger.log(err)
                    continue
            else:
                self.slave_loop()

    def election(self):
        """
        Begins establishing master node in the network
        """

        self.change_color('init')
        self.logger.log('Attempting to establish new master')

        # Send election message to nodes with higher id
        for node_id in range(self.id + 1, self.max_node_id + 1):
            self.messenger.send_message(
                node_id=node_id,
                endpoint='election',
                value=self.id,
            )

        # Reset state
        self.is_master, self.surrendered = False, False

        # Setup election timeout
        election_timeout = Timeout(MAX_ELECTION_DURATION_SECS)
        while True:
            message = self.read_next_message(ELECTION_MSG_QUEUE_SLEEP_SECS)
            if election_timeout.timed_out():
                if not self.surrendered:
                    self.declare_self_as_master()
                    return

                raise ElectionUnsuccessfulException(
                    f'Election unsuccessful, will attempt again in {ELECTION_UNSUCESSFUL_SLEEP_SECS} seconds...'
                )

            if message is None:
                continue

            if message.key != 'election':
                continue  # Ignore non-election messages

            election_finished = self.handle_election_message(
                message, election_timeout)
            if election_finished:
                break

    def handle_election_message(self, message: Message, timeout: Union[None, Timeout] = None):
        """
        Handles single election message.

        Args:
            message (Message): election message

        Returns:
            str: to signal whether to exit the election loop
        """

        if message.value == 'victory' and message.sender_id > self.id:
            # We have received a victory message from another node
            if self.master_id is not None and self.master_id == message.sender_id:
                return False

            self.master_id = message.sender_id
            self.is_master = False
            self.logger.log(
                f'Master (NODE-{self.master_id + 1}) has been established via victory message...')
            return True

        if message.value == 'surrender' and not self.surrendered:
            # We have received a surrender message from another node
            # This means that we won't be the master
            self.logger.log(
                f'Found node with higher id (NODE-{message.sender_id + 1}), surrendering...')

            if timeout is not None:
                # In case timeout is used extend it so that we give master time to announce the results
                timeout.extend(ELECTION_EXTENSION_SECS)

            self.surrendered = True

        elif isinstance(message.value, int) and message.value < self.id:
            self.logger.log(
                f'Found node with lower id (NODE-{message.value + 1}), sending surrender message...')
            self.messenger.send_message(
                node_id=message.sender_id,
                endpoint='election',
                value='surrender',
            )

        return False

    def check_for_cluster_changes(self, message: Message, finding_active_nodes=False):
        """
        Used in master loop - returns True if cluster reconfiguration is necessary.
        This may be caused by new node joining the cluster, or by node with higher id joining

        Args:
            message (Message): message with key 'election'
            finding_active_nodes (bool, optional): If True the method won't trigger cluster reset for nodes trying to
                                                   start an election and will only send them victory message
        """
        if not message.key == 'election':
            return

        if isinstance(message.value, int) and message.value < self.id:
            self.messenger.send_message(
                endpoint='election',
                value='victory',
                node_id=message.sender_id,
            )
            # New node joined the cluster, we need to recolor the nodes
            if not finding_active_nodes and message.sender_id not in self.alive_nodes:
                raise ClusterResetException(
                    f'Detected new node (NODE-{message.value + 1}) trying to join the cluster, sending victory message and recoloring the cluster...')

        # If we receive victory we need to stop master loop immediately and
        # start slave loop
        elif message.value == 'victory' and message.sender_id > self.id:
            self.master_id = message.sender_id
            self.is_master = False
            raise ClusterResetException(
                f'New master (NODE-{self.master_id + 1}) has been established via victory message. Stopping master loop...')

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

    def find_active_nodes(self):
        """
        Finds all active nodes in the network. 
        Clears internal state of alive nodes and their colors
        """

        self.alive_nodes.clear()
        self.node_colors.clear()
        self.nodes_to_color.clear()

        # Send broadcast to all nodes with heartbeat request
        for node_id in range(self.max_node_id + 1):
            if node_id == self.id:
                continue

            self.messenger.send_message(
                endpoint='heartbeat',
                node_id=node_id,
                value='request',
            )

        # Wait for the responses
        # Nodes have up to NODE_ALIVE_TIMEOUT_SECS to respond
        search_timeout = Timeout(NODE_ALIVE_TIMEOUT_SECS)
        while True:
            if len(self.alive_nodes) == self.max_node_id + 1:
                # All possbile nodes are alive
                break

            message = self.read_next_message(
                timeout_secs=HEARTBEAT_INTERVAL_SECS)
            if message is None or search_timeout.timed_out():
                break

            self.check_for_cluster_changes(message, finding_active_nodes=True)

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

        # Similarly to color the nodes we have some fixed timeout to wait for the responses
        color_assignment_timeout = Timeout(MAX_COLOR_ASSIGNMENT_DURATION_SECS)
        while True:
            if len(self.nodes_to_color) == 0:
                break

            message = self.read_next_message(
                MAX_COLOR_ASSIGNMENT_DURATION_SECS)
            if message is None or color_assignment_timeout.timed_out():
                break

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
                    node_id=message.sender_id,
                    endpoint='heartbeat',
                    value='response',
                )

        return len(self.nodes_to_color) == 0

    def setup_colors(self):
        """
        Setups colors for each node in the cluster
        """

        self.logger.log('Setting up node colors...')

        # Find active nodes
        self.find_active_nodes()
        
        n_tries = self.n_color_tries
        self.assign_colors()

        # Color the nodes
        while n_tries > 0:
            for node_id, color in self.nodes_to_color.items():
                self.messenger.send_message(
                    node_id=node_id,
                    endpoint='color',
                    value=color,
                )

            if self.all_colors_assigned():
                self.logger.log('All nodes have been colored.')
                self.print_node_colors()
                return
            else:
                n_tries -= 1

        raise ClusterResetException(
            'Error, not all nodes have been colored, retrying...')

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

        heartbeat_timeout = Timeout(HEARTBEAT_INTERVAL_SECS)
        self.master_timeout = Timeout(NODE_ALIVE_TIMEOUT_SECS)
        self.change_color('slave')
        while True:
            # If master did not respond until timeout start election
            # i.e. break out of the loop and set flags that will trigger it
            if self.master_timeout.timed_out():
                self.logger.log(
                    f'Master (NODE-{self.master_id + 1}) did not respond, starting an election')
                self.is_master = False
                self.master_id = None
                break

            # Send heartbeat request to master if timeout reached
            if heartbeat_timeout.timed_out():
                self.messenger.send_message(
                    node_id=self.master_id,
                    endpoint='heartbeat',
                    value='request',
                )
                heartbeat_timeout.reset()

            message = self.read_next_message(HEARTBEAT_INTERVAL_SECS)
            if message is None:
                continue

            # If we get an election message we handle it in a handle_election_message
            # This can be e.g. new node joining the cluster or new master having been
            # elected
            if message.key == 'election':
                # For slave we obviously only care for the master
                new_master = self.handle_election_message(message)
                if new_master:
                    return  # From here we will enter "slave_setup" again

            if message.sender_id != self.master_id:
                continue  # Ignore messages that are not from master and were not election ones

            # In all cases now we got something from master, which means they are alive
            self.master_timeout.reset()

            # If we get a heartbeat message we simply respond back
            if message.key == 'heartbeat':
                if message.value == 'request':
                    self.messenger.send_message(
                        node_id=message.sender_id,
                        endpoint='heartbeat',
                        value='response',
                    )
                else:
                    self.logger.log(
                        f'Received heartbeat response from master (NODE-{self.master_id + 1})')

            # Lastly we handle the color message
            if message.key == 'color':
                self.change_color(message.value)
                self.messenger.send_message(
                    node_id=self.master_id,
                    endpoint='color',
                    value=self.color
                )

    def check_slave_timeouts(self, slave_timeouts: dict):
        """
        Checks whether any slave has timed out

        Args:
            slave_timeouts (dict): dictionary containing timeout for each slave

        Returns:
            bool: True if any slave has timed out, False otherwise
        """

        for node_id, timeout in slave_timeouts.items():
            if timeout.timed_out():
                raise ClusterResetException(
                    f'NODE-{node_id + 1} did not respond, recoloring the cluster...')

    def master_loop(self):
        """
        Loop for master mode.
        """

        # Create timeouts for each slave
        # Each slave must send heartbeat request to master which will update its timeout
        check_for_timeouts = Timeout(NODE_ALIVE_TIMEOUT_SECS / 2)
        slave_timeouts = {
            slave_id: Timeout(NODE_ALIVE_TIMEOUT_SECS) for slave_id in self.alive_nodes
        }

        while True:
            message = self.read_next_message(0.5)

            if check_for_timeouts.timed_out():
                self.check_slave_timeouts(slave_timeouts)

            if message is None:
                # If no message is avaialble continue sleeping
                continue

            self.check_for_cluster_changes(message)

            if message.sender_id not in self.alive_nodes:
                continue

            # Slaves must send heartbeat request to master
            if message.key == 'heartbeat':
                slave_timeouts[message.sender_id].reset()  # reset the timer
                self.logger.log(
                    f'Received heartbeat from NODE-{message.sender_id + 1}')
                self.messenger.send_message(
                    node_id=message.sender_id,
                    endpoint='heartbeat',
                    value='response',
                )
