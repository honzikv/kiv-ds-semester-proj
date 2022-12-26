# This module is responsible for connecting the node to the
# cluster. It will register itself with the zookeeper cluster
# after callign the register_zoonode function

import logging_factory
import time

from env import NODE_NAME, ROOT_NODE, ZOOKEEPER
from kazoo.client import KazooClient

WAIT_INTERVAL_SECS = 5
N_RETRIES = 5

__logger = logging_factory.create_logger('cluster_connector')

# Create a zookeeper client
__kazoo_client = KazooClient(hosts=ZOOKEEPER)
__kazoo_client.start()


def __register_path(path: str):
    """
    Registers specified path to the zookeeper cluster.
    Throws an error if the path already exists.

    Args:
        path (str): path to register
    """
    if __kazoo_client.exists(path):
        __logger.critical(
            f'Node {path} already exists. The process cannot continue, exiting...')
        exit(1)

    __kazoo_client.create(path=path, makepath=True)


def register_node(parent_path: str = None):
    """
    Registers node within the cluster.

    Args:
        parent_path (str): path of the parent - this is obtained from the root node. Use None for root node.
    """

    if NODE_NAME == ROOT_NODE:
        # Register the root node
        __logger.info('Registering root node')
        __register_path(f'/{ROOT_NODE}')
        return

    for _ in range(N_RETRIES):
        if not __kazoo_client.exists(parent_path):
            __logger.info(
                f'Parent node {parent_path} does not exist. Retrying...')
            time.sleep(WAIT_INTERVAL_SECS)
            continue

        # Otherwise we can register the node
        __register_path(f'{parent_path}/{NODE_NAME}')
        break
    else:
        # This only executes if the for loop is not broken
        __logger.critical('Could not register node. Exiting...')
        exit(1)
