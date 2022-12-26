import cluster.zookeeper_connector as zookeeper_connector

from fastapi import APIRouter

# Simple module that represents a data store

__store = {}

# Router to define api endpoints
store_router = APIRouter()


@store_router.get('/{key}')
async def get_item(key: str):
    if key in __store:
        # TODO perform master check or something
        return {'item': __store[key]}

    # Otherwise try to contact the top node
    res = await zookeeper_connector.get_key_from_parent(key)

    # Update the key in the store
    item = res['item']
    __store[key] = item

    # Return the value
    return {'success': item is not None, 'item': item}


@store_router.put('/{key}')
async def put_item(key: str, value):
    # Update the value locally
    __store[key] = value

    # Update it in the parent node
    res = await zookeeper_connector.put_key_in_parent(key, value)
    if not res['success']:
        return {'success': False, 'error': 'Failed to update parent node', 'key': key, 'value': value}

    return {'success': True, 'key': key, 'value': value}


@store_router.delete('/{key}')
async def delete_item(key: str):
    # Delete the value locally
    __store.pop(key, None)

    # Delete it in the parent node
    res = await zookeeper_connector.delete_key_from_parent(key)
    if not res['success']:
        return {'success': False, 'error': 'Failed to delete from parent node', 'key': key}

    return {'success': True, 'key': key}