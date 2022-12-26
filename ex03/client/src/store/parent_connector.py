# This module serves as a HTTP client wrapper for communication with parent node

import logging_factory
import httpx
import asyncio

from typing import Any
from env import ROOT_NODE, NODE_NAME

# Name of the parent node, None if this node is root
__parent_node = None
__logger = logging_factory.create_logger('parent_connector')


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


def get_key_from_parent(key: str):
    """
    Gets key from parent node.

    Args:
        key (str): key to get
    """

    if __parent_node is None:
        return {'item': None}

    res = httpx.get(f'http://{__parent_node}/store/{key}')
    if res.status_code == 200:
        return res.json()
    elif res.status_code == 404:
        return {'item': None}

    raise Exception(
        f'Could not get key {key} from parent node {__parent_node}')


async def put_key_in_parent(key: str, value: Any, wait_for_response: bool = False):
    """
    Puts key in the parent node.

    Args:
        key (str): key to be put
        value (Any): value to be put
        req (PutKeyRequest): request body
    """

    if __parent_node is None:
        return {'success': True}

    if wait_for_response:
        res = httpx.put(f'http://{__parent_node}/store/{key}',
                        json={'key': key, 'value': value, '_wait_for_parent': False})
        if res.status_code == 200:
            return {'success': True}
        return {'success': False}

    # Otherwise just send the request and return
    async def put_async():
        async with httpx.AsyncClient() as client:
            res = await client.put(f'http://{__parent_node}/store/{key}', json={'key': key, 'value': value, '_wait_for_parent': False})
            if res.status_code != 200:
                __logger.error(
                    f'Could not put key {key} in parent node {__parent_node}')

    asyncio.create_task(put_async())
    return {'success': True}


async def delete_key_in_parent(key: str, wait_for_response: bool = False):
    """
    Deletes key from parent node.

    Args:
        key (str): key to be deleted
    """

    if __parent_node is None:
        return {'success': True}

    if wait_for_response:
        res = httpx.delete(
            f'http://{__parent_node}/store/{key}?wait_for_parent=false')
        if res.status_code == 200:
            return {'success': True}
        return {'success': False}

    async def delete_async():
        async with httpx.AsyncClient() as client:
            res = await client.delete(f'http://{__parent_node}/store/{key}?wait_for_parent=false')
            if res.status_code != 200:
                __logger.error(
                    f'Could not delete key {key} from parent node {__parent_node}')

    asyncio.create_task(delete_async())
    return {'success': True}
