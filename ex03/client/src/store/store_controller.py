# This simple module represents a datastore
# For simplicity store is a dictionary

import store.store_service as store_service
import logging_factory

from fastapi import APIRouter
from typing import Any
from pydantic import BaseModel


__store = {}

__logger = logging_factory.create_logger('store')

# Router to define api endpoints
store_router = APIRouter()


class PutKeyRequest(BaseModel):
    """
    JSON model for put key request.
    """
    value: Any
    _wait_for_parent: bool = True


@store_router.get('/store/{key}')
def get_item(key: str):
    """
    Returns the value of the key from the store. If the key is not present in the store,
    the request is propagated to the parent node recursively.

    Args:
        key (str): key to get

    Returns:
        json: with "success" and "value" fields
    """
    
    if key in __store:
        __logger.debug(f'Found key {key} in the local store, returning it...')
        return {'value': __store[key]}

    # Otherwise try to contact the top node
    try:
        res = store_service.get_key_from_parent(key)
    except Exception as e:
        __logger.error(f'Failed to get key {key} from parent node: {e} due to communication issues')
        return {'success': False, 'error': 'Failed to get key from parent node due to communication issues'}, 503

    # Update the key in the store
    value = res['value']
    __store[key] = value

    # Return the value
    return {'success': value is not None, 'value': value}, 200 if value is not None else 404


@store_router.put('/store/{key}')
async def put_item(key: str, put_key_req: PutKeyRequest):
    """
    Puts key in the store. This is propagated to the parent node recursively.
    Uses PutKeyRequest to pass the value and whether to wait for parent response.

    Args:
        key (str): key to be put
        put_key_req (PutKeyRequest): request body

    Returns:
        json: with "success", "key" and "value" fields
    """
    
    # Update the value locally
    __store[key] = put_key_req.value

    # Update it in the parent node
    req = PutKeyRequest(key=key, value=put_key_req.value,
                        _wait_for_parent=False)
    
    try:
        _ = store_service.put_key_in_parent(
            key, req, wait_for_response=put_key_req._wait_for_parent)
    except Exception:
        __logger.error(f'Failed to update parent node for key {key} due to communication issues')
        return {'success': False, 'error': 'Failed to update parent node due to communication issues', 'key': key, 'value': req.value}, 503

    return {'success': True, 'key': key, 'value': req.value}


@store_router.delete('/store/{key}')
async def delete_item(key: str, wait_for_parent: bool = True):
    """
    Deletes key from the store. This is propagated to the parent node recursively.
    If wait_for_parent is set to False, the request is sent asynchronously.

    Args:
        key (str): key to be deleted
        wait_for_parent (bool, optional): Whether to wait for parent response. Defaults to True.

    Returns:
        json: with "success" and "key" fields
    """
    
    # Update the value locally
    __store.pop(key, None)

    # Delete it in the parent node
    try:
        _ = store_service.delete_key_in_parent(
            key, wait_for_parent=wait_for_parent)
    except Exception:
        __logger.error(f'Failed to delete key {key} from parent node due to communication issues')
        return {'success': False, 'error': 'Failed to delete key from parent node due to communication issues'}, 503

    return {'success': True, 'key': key}


@store_router.get('/store')
def get_all_items():
    """
    Returns all items in the store as json

    Returns:
        json: __store contents
    """
    return __store
