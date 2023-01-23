from typing import Union
import fire
import httpx
import os
import re
import json

config = json.load(open('conf.json'))

mode = config['mode']
node_url_prefix = config['node_url_prefix']
port_start = config['port_start']
node_prefix = config['node_prefix']
NODE_REGEX = f'{node_prefix}[0-9]+'


def create_node_url(node_id):
    if mode == 'host':
        return f'{node_url_prefix}{port_start + node_id}'
    
    return f'{node_url_prefix}{node_id}:{port_start}'


def build_node_url(node_str: str):
    """
    Build node url from specified string input

    Args:
        node_str (str): string input (or possibly int)

    Raises:
        ValueError: if node_str is not a valid node name

    Returns:
        str: base url for the given node
    """
    try:
        node_id = int(node_str)
    except ValueError:
        if not re.match(NODE_REGEX, node_str, re.IGNORECASE):
            raise ValueError('Invalid node name')

        node_id = int(node_str[len(node_prefix):])

    node_url = create_node_url(node_id)
    return node_url


def put(node: str, key: str, value: Union[str, int, float, bool]):
    """
    Sets key in the specified node to the given value.

    Args:
        node (str): name of the node. E.g. NODE-1 (case-insensitive), can also be just 1
        key (str): Key to set
        value (Union[str, int, float, bool]): value to set - this can be string, int, float or bool
    """
    try:
        node_url = build_node_url(node)
        res = httpx.put(f'{node_url}/store/{key}', json={'value': value})
        print(f'{res.status_code} {res.json()}')

    except Exception as e:
        print(e)
        return


def get(node: str, key: str):
    """
    Gets value of the given key from the specified node.

    Args:
        node (str): name of the node. E.g. NODE-1 (case-insensitive), can also be just 1
        key (str): Key to get
    """
    try:
        node_url = build_node_url(node)
        res = httpx.get(f'{node_url}/store/{key}')
        print(f'{res.status_code} {res.json()}')

    except Exception as e:
        print(e)
        return


def delete(node: str, key: str):
    """
    Deletes the given key from the specified node.

    Args:
        node (str): name of the node. E.g. NODE-1 (case-insensitive), can also be just 1
        key (str): key to delete
    """
    try:
        node_url = build_node_url(node)
        res = httpx.delete(f'{node_url}/store/{key}')
        print(f'{res.status_code} {res.json()}')

    except Exception as e:
        print(e)
        return


if __name__ == '__main__':
    fire.Fire({
        'put': put,
        'PUT': put,
        'get': get,
        'GET': get,
        'delete': delete,
        'DELETE': delete,
    })
