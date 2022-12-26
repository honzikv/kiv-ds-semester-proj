import parent_connector
import logging_factory

from fastapi import APIRouter
from store_models import PutKeyRequest

# Simple module that represents a data store

__store = {}

__logger = logging_factory.create_logger('store')

# Router to define api endpoints
store_router = APIRouter()


@store_router.get('/{key}')
def get_item(key: str):
    if key in __store:
        # TODO perform master check or something
        return {'item': __store[key]}

    # Otherwise try to contact the top node
    try:
        res = parent_connector.get_key_from_parent(key)
    except Exception as e:
        __logger.critical(f'Failed to get key {key} from parent node: {e}')
    
    # Update the key in the store
    item = res['item']
    __store[key] = item

    # Return the value
    return {'success': item is not None, 'item': item}, 200 if item is not None else 404


@store_router.put('/{key}')
async def put_item(key: str, put_key_req: PutKeyRequest):
    # Update the value locally
    __store[key] = put_key_req.value

    # Update it in the parent node
    req = PutKeyRequest(key=key, value=put_key_req.value, _wait_for_parent=False)
    res = parent_connector.put_key_in_parent(key, req, wait_for_response=put_key_req._wait_for_parent)
    if not res['success']:
        return {'success': False, 'error': 'Failed to update parent node', 'key': key, 'value': req.value}

    return {'success': True, 'key': key, 'value': req.value}


@store_router.delete('/{key}')
async def delete_item(key: str, wait_for_parent: bool = True):
    # Delete the value locally
    __store.pop(key, None)

    # Delete it in the parent node
    res = parent_connector.delete_key_in_parent(key, wait_for_parent=wait_for_parent)
    if not res['success']:
        return {'success': False, 'error': 'Failed to delete from parent node', 'key': key}

    return {'success': True, 'key': key}
