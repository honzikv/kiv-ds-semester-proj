# This simple module represents a datastore
# For simplicity store is a dictionary

import store.store_service as store_service
import logging_factory

from fastapi import APIRouter, HTTPException
from typing import Any
from pydantic import BaseModel

# Store is represented by a dictionary
__store = {}

__logger = logging_factory.create_logger(__name__)

# Router to define api endpoints
store_router = APIRouter()


class PutKeyRequest(BaseModel):
    """
    JSON model for put key request.
    """
    value: Any
    wait_for_parent: bool = True


@store_router.get('/store/{key}')
def get_item(key: str):
    """
    Returns the value of the key from the store. If the key is not present in the store,
    the request is propagated to the parent node recursively.

    Args:
        key (str): key to get

    Returns:
        json: with and "value" field
    """
    
    if key in __store:
        __logger.debug(f'Found key {key} in the local store, returning it...')
        return {'value': __store[key]}

    # Otherwise try to contact the top node
    try:
        res = store_service.get_key_from_parent(key)
    except Exception as e:
        __logger.error(f'Failed to get key {key} from parent node: {e}')
        raise HTTPException(status_code=503, detail='Failed to get key from parent node due to communication issues')

    # Update the key in the store
    value = res['value']
    __store[key] = value

    # Return the value
    if value is not None:
        return {'value': value}
    
    raise HTTPException(status_code=404, detail='Key not found')


@store_router.put('/store/{key}')
def put_item(key: str, put_key_req: PutKeyRequest):
    """
    Puts key in the store. This is propagated to the parent node recursively.
    Uses PutKeyRequest to pass the value and whether to wait for parent response.

    Args:
        key (str): key to be put
        put_key_req (PutKeyRequest): request body

    Returns:
        json: with "key" and "value" fields
    """
    
    # Update the value locally
    __store[key] = put_key_req.value
    
    try:
        _ = store_service.put_key_in_parent(
            key, put_key_req.value, wait_for_response=put_key_req.wait_for_parent)
    except Exception as e:
        err = f'Failed to update key {key} in parent node due to communication issues'
        __logger.error(err)
        raise HTTPException(status_code=503, detail=err)

    return {'key': key, 'value': put_key_req.value}


@store_router.delete('/store/{key}')
def delete_item(key: str, wait_for_parent: bool = True):
    """
    Deletes key from the store. This is propagated to the parent node recursively.
    If wait_for_parent is set to False, the request is sent in the background.

    Args:
        key (str): key to be deleted
        wait_for_parent (bool, optional): Whether to wait for parent response. Defaults to True.

    Returns:
        json: with key" field
    """
    
    # Update the value locally
    __store.pop(key, None)

    # Delete it in the parent node
    try:
        _ = store_service.delete_key_in_parent(
            key, wait_for_parent=wait_for_parent)
    except Exception:
        err = f'Failed to delete key {key} from parent node due to communication issues'
        __logger.error(err)
        raise HTTPException(status_code=503, detail=err)

    return {'key': key}


@store_router.get('/store')
def get_all_items():
    """
    Returns all items in the store as json

    Returns:
        json: __store contents
    """
    return __store
