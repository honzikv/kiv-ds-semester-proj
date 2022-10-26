import os
import argparse
from node import Node

# Local development without docker for easier testing
localhost = '127.0.0.1'
local_addrs = [(localhost, 2333), (localhost, 2334)]

if __name__ == '__main__':

    argparser = argparse.ArgumentParser()
    argparser.add_argument('--node_addr', type=int, required=True, help='Address of this node')
    args = argparser.parse_args()

    node = Node(node_addr=local_addrs[args.node_addr], node_addrs=local_addrs)
    node.run()


