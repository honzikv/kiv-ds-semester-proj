from typing import List, Optional
from env import ROOT_NODE, N_NODES

__binary_tree = [ROOT_NODE] + [None] * (N_NODES - 1)
__next_idx = 1


def __add_node(node_name: str):
    """
    Adds node to the binary tree.

    Args:
        node_name (str): node name
    """
    global __binary_tree, __next_idx

    __binary_tree[__next_idx] = node_name
    __next_idx += 1


def __get_parent_node_idx(node_idx: int) -> int:
    """
    Returns the parent node index of the given node index.

    Args:
        node_idx (int): index of the node

    Returns:
        int: index of the parent node
    """
    return int((node_idx + 1) / 2) - 1


def find_absolute_parent_path(node_name: str) -> str:
    """
    Finds absolute parent path for the given node.
    This function automatically adds the node if it doesn't exist.

    Args:
        node_name (str): name of the node

    Returns:
        str: absolute parent path starting with /. This can be directly used in the zoookeeper client.
    """

    try:
        node_idx = __binary_tree.index(node_name)
    except ValueError:
        # Add the node if it doesn't exist
        node_idx = __next_idx
        __add_node(node_name)

    # Get parent
    parent_node_id = __get_parent_node_idx(node_idx)
    parent = __binary_tree[parent_node_id]
    path = [parent_node_id]

    # Loop until we get to the root node
    while parent_node_id != 0:
        parent_node_id = __get_parent_node_idx(parent_node_id)
        parent = __binary_tree[parent_node_id]
        path.append(parent)

    # Add '' to make the string start with /
    path.append('')
    # join items with / and return in reverse order
    return '/'.join(path[::-1])


def get_structure() -> List[Optional[str]]:
    """
    Returns shallow copy of the current tree

    Returns:
        List[str]: shallow copy of the current tree
    """
    return __binary_tree.copy()
