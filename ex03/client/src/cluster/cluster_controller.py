import cluster.cluster_structure as cluster_structure

from fastapi import APIRouter

# This is only used in the root node
cluster_router = APIRouter()


@cluster_router.get('/nodes/parent/{node_name}')
def find_absolute_parent_path(node_name: str):
    """
    Returns absolute parent path for the given node.

    Args:
        node_name (str): name of the node, e.g. NODE-1

    Returns:
        str: absolute parent path starting with `/` This can be directly used in the zoookeeper client.
    """
    node_name = node_name.upper()
    return {'path': cluster_structure.find_absolute_parent_path(node_name)}


@cluster_router.get('/nodes/structure')
def get_tree():
    """
    Returns array representation of the binary tree.

    Returns:
        list: Binary tree array
    """
    return {'binary_tree_array': cluster_structure.get_structure()}
