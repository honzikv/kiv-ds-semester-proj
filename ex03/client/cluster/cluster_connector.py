# This module serves as a HTTP client wrapper for communication with parent node

from env import ROOT_NODE, NODE_NAME

# Name of the parent node, None if this node is root
__parent_node = None


def initialize_cluster_connector(parent_path: str):
    """
    Initializes the cluster connector module.

    Args:
        parent_path (str): parent path
    """
    global __parent_node
    
    # Keep the value None if this is the root node
    if NODE_NAME == ROOT_NODE:
        return
    
    __parent_node = parent_path.split('/')[-1]
    

