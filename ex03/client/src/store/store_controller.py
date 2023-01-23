# This simple module represents a datastore
# For simplicity store is a dictionary
# In a real world scenario we would separate the layers but since this
# is a simple example we will keep it in one file

import store.store_service as store_service
import logging_factory

from fastapi import APIRouter, HTTPException
from typing import Any
from pydantic import BaseModel

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

    # Update the key in the store if not None and return it
    value = res['value']
    if value is not None:
        __store[key] = value
        return {'value': value}
    
    # Otherwise return 404 since there is no such value
    raise HTTPException(status_code=404, detail='Key not found')


@store_router.put('/store/{key}')
def put_item(key: str, put_key_req: PutKeyRequest):
    """
    Puts key in the store. This is propagated to the parent node recursively.
    Uses PutKeyRequest to pass the value and whether to wait for parent response.
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
    """
    
    # Update the value locally
    if key in __store:
        del __store[key]

    # Delete it in the parent node
    try:
        _ = store_service.delete_key_in_parent(key, wait_for_parent=wait_for_parent)
    except Exception as e:
        __logger.error(f'Failed to delete key {key} in parent node: {e}')
        raise HTTPException(status_code=503, detail=f'Failed to delete key {key} from parent node due to communication issues')

    return {'key': key}


@store_router.get('/store')
def get_all_items():
    """
    Returns all items in the store as json
    """
    return __store
