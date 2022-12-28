# This module serves as a HTTP client wrapper for communication with parent node

import logging_factory
import httpx
import asyncio
import background_tasks

from typing import Any
from env import ROOT_NODE, NODE_NAME

# Name of the parent node, None if this node is root
__parent_node = None

__logger = logging_factory.create_logger('parent_connector')


def set_parent(parent_path: str):
    """
    Initializes the service.

    Args:
        parent_path (str): parent path
    """
    global __parent_node

    # Keep the value None if this is the root node
    if NODE_NAME == ROOT_NODE:
        return

    __parent_node = parent_path.split('/')[-1]
    __logger.debug(f'Parent node set to {__parent_node}')


def get_key_from_parent(key: str):
    """
    Gets key from parent node.

    Args:
        key (str): key to get
    """

    if __parent_node is None:
        return {'value': None}

    res = httpx.get(f'http://{__parent_node}/store/{key}')
    if res.status_code == 200:
        return res.json()
    elif res.status_code == 404:
        return {'value': None}

    raise Exception(
        f'Could not get key {key} from parent node {__parent_node}')


def put_key_in_parent(key: str, value: Any, wait_for_response: bool = False):
    """
    Puts key in the parent node.

    Args:
        key (str): key to be put
        value (Any): value to be put
        req (PutKeyRequest): request body
    """

    if __parent_node is None:
        __logger.debug(f'There is no parent - this is a root node, skipping put key "{key}"')
        return {'success': True}

    if wait_for_response:
        res = httpx.put(f'http://{__parent_node}/store/{key}',
                        json={'key': key, 'value': value, '_wait_for_parent': False})
        if res.status_code == 200:
            __logger.debug(f'Put key "{key}" in parent node {__parent_node}')
            return {'success': True}
        
        __logger.error(f'Put request failed, got status code {res.status_code}')
        raise Exception(
            f'Could not put key "{key}" in the parent node {__parent_node}')

    # Otherwise just send the request and return
    def put_in_background():
        res = httpx.put(f'http://{__parent_node}/store/{key}',
                        json={'key': key, 'value': value, '_wait_for_parent': False})
        if res.status_code == 200:
            __logger.debug(f'Async put key {key} in parent node {__parent_node}')
            return {'success': True}
            
        __logger.debug(f'Async put key {key} in parent node {__parent_node} failed')
        
    background_tasks.add_task(put_in_background)
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
        raise Exception(f'Could not delete key "{key}" from parent node due to error')
    
    # Otherwise do it in the background
    async def delete_in_background():
        res = httpx.delete(
            f'http://{__parent_node}/store/{key}?wait_for_parent=false')
        __logger.debug(f'Async delete key "{key}" in parent node {__parent_node} succeeded')
        if res.status_code != 200:
            __logger.debug(f'Async delete key "{key}" in parent node {__parent_node} failed')
            
    background_tasks.add_task(delete_in_background)
    return {'success': True}
