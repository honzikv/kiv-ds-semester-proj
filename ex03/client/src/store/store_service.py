# This module serves as a HTTP client wrapper for communication with parent node

import logging_factory
import httpx
import asyncio
import background_tasks

from typing import Any
from env import ROOT_NODE, NODE_NAME, API_PORT

# Name of the parent node, None if this node is root
__parent_node = None

__logger = logging_factory.create_logger(__name__)


def __build_url(path: str) -> str:
    """
    Builds the URL for the given path.

    Args:
        path (str): path to be appended to the base URL

    Returns:
        str: URL
    """
    return f'http://{__parent_node}:{API_PORT}/{path}'


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

    url = __build_url(f'store/{key}')
    __logger.debug(f'Sending GET request to {url}')
    res = httpx.get(url)

    if res.status_code == 200:
        return res.json()
    elif res.status_code == 404:
        return {'value': None}

    raise Exception(
        f'Could not get key {key} from parent node {__parent_node}')


def put_in_background(url, key, value):
    """
    Performs PUT request in the background.

    Args:
        url (str): _description_
        key (str): _description_
        value (Any): _description_
    """
    res = httpx.put(
        url, json={'value': value, 'wait_for_parent': False})
    if res.status_code == 200:
        __logger.debug(
            f'Async put key {key} in parent node {__parent_node}')
        return

    __logger.debug(
        f'Async put key {key} in parent node {__parent_node} failed')


def put_key_in_parent(key: str, value: Any, wait_for_response: bool = False):
    """
    Puts key in the parent node.

    Args:
        key (str): key to be put
        value (Any): value to be put
        req (PutKeyRequest): request body
    """

    if __parent_node is None:
        __logger.debug(
            f'There is no parent - this is a root node, skipping put key "{key}"')
        return {'success': True}

    url = __build_url(f'store/{key}')
    __logger.debug(
        f'Sending PUT request to {url}, wait_for_response={wait_for_response}')
    if wait_for_response:
        res = httpx.put(
            url, json={'value': value, 'wait_for_parent': False})

        if res.status_code == 200:
            __logger.debug(f'Put key "{key}" in parent node {__parent_node}')
            return {'success': True}

        __logger.error(
            f'Put request failed, got status code {res.status_code}')
        raise Exception(
            f'Could not put key "{key}" in the parent node {__parent_node}')

    # Otherwise just send the request and return
    __logger.debug('Sending PUT request in background...')
    background_tasks.add_task(lambda: put_in_background(url, key, value))
    return {'success': True}


def delete_in_background(url, key):
    """
    Performs a DELETE request in the background.

    Args:
        url (str): URL to send the request to
        key (key): key
    """
    res = httpx.delete(url)
    if res.status_code != 200:
        __logger.debug(
            f'Async delete key "{key}" in parent node {__parent_node} failed')
        return

    __logger.debug(
        f'Async delete key "{key}" in parent node {__parent_node} succeeded')


def delete_key_in_parent(key: str, wait_for_response: bool = False):
    """
    Deletes key from parent node.

    Args:
        key (str): key to be deleted
    """

    if __parent_node is None:
        return {'success': True}

    url = __build_url(f'store/{key}?wait_for_parent=false')
    __logger.debug(f'Sending DELETE request to {url}')

    if wait_for_response:
        res = httpx.delete(url)
        if res.status_code == 200:
            return {'success': True}
        raise Exception(
            f'Could not delete key "{key}" from parent node due to error')

    __logger.debug('Sending DELETE request in background...')
    background_tasks.add_task(lambda: delete_in_background(url, key))
    return {'success': True}
