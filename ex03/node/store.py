from fastapi import APIRouter

# Simple module that represents a data store

_store = {}

# Router to define api endpoints
store_router = APIRouter()


@store_router.get('/')
async def get_item(item: str):
    if item in _store:
        # TODO perform master check or something
        return {'success': True, 'item': _store[item]}
    
    # Otherwise try to contact bottom or top node
    
