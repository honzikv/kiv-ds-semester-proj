from typing import Union
import fire
import httpx
import os
import re

MODE = 'host' if not os.environ.get('docker') else 'guest'
NODE_URL_PREFIX = 'http://localhost:' if MODE == 'host' else 'http://NODE-'
PORT_START = 5000
NODE_PREFIX = 'NODE-'
NODE_REGEX = f'{NODE_PREFIX}[0-9]+'


def create_node_url(node_id):
    if MODE == 'host':
        return f'{NODE_URL_PREFIX}{PORT_START + node_id}'
    
    return f'{NODE_URL_PREFIX}{node_id}:{PORT_START}'


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

        node_id = int(node_str[len(NODE_PREFIX):])

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

        if res.status_code != 200:
            print(f'Error: {res.status_code} {res.json()}')
        else:
            print(res.json())

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

        if res.status_code != 200:
            print(f'Error: {res.status_code} {res.json()}')
        else:
            print(res.json())

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

        if res.status_code != 200:
            print(f'Error: {res.status_code} {res.json()}')
        else:
            print(res.json())

    except Exception as e:
        print(e)
        return


if __name__ == '__main__':
    fire.Fire({
        'put': put,
        'get': get,
        'delete': delete,
    })
