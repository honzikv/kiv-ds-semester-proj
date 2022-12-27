# Simple module that extracts all necessary environment variables
# so that they do not need to be queried via os.environ every time

import os

ZOOKEEPER = os.environ['zookeeper']
NODE_NAME = os.environ['node_name']
NODE_ADDRESS = os.environ['node_address']
ROOT_NODE = os.environ['root_node']
N_NODES = int(os.environ['n_nodes'])
API_PORT = int(os.environ['api_port'])
STARTUP_DELAY = int(os.environ['startup_delay'])

if os.environ['debug']:
    print(f'ZOOKEEPER = {ZOOKEEPER}')
    print(f'NODE_NAME = {NODE_NAME}')
    print(f'ROOT_NODE = {ROOT_NODE}')
    print(f'N_NODES = {N_NODES}')
    print(f'API_PORT = {API_PORT}')
    print(f'STARTUP_DELAY = {STARTUP_DELAY}', flush=True)