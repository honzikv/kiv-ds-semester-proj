# Simple module that extracts all necessary environment variables
# so that they do not need to be queried via os.environ every time

import os

ZOOKEEPER = os.environ['zookeeper']
NODE_NAME = os.environ['node_name']
ROOT_NODE = os.environ['root_node']
N_NODES = int(os.environ['n_nodes'])
API_PORT = int(os.environ['api_port'])
STARTUP_DELAY = int(os.environ['startup_delay'])