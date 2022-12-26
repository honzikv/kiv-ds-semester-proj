import fastapi
import time
import httpx
import logging
import logging_factory
import uvicorn
import cluster.zookeeper_connector as zookeeper_connector

from env import NODE_NAME, ROOT_NODE, API_PORT, STARTUP_DELAY
from cluster.cluster_controller import cluster_router
from store.store_controller import store_router

__logger = logging_factory.create_logger('main')

# Create fastapi app
app = fastapi.FastAPI()
app.include_router(store_router)

# Add corresponding components
if NODE_NAME == ROOT_NODE:
    app.include_router(cluster_router)
    
    # Register the root node straight away before starting the server
    zookeeper_connector.register_node()
else:
    # Sleep for some time to allow the root node to start
    time.sleep(STARTUP_DELAY)

    # Define startup event that will call the root node to register itself
    # and register the node with the cluster
    @app.on_event('startup')
    async def on_start():
        res = httpx.get(
            f'http://{ROOT_NODE}:{API_PORT}/nodes/parent/{NODE_NAME}')
        __logger.info(f'Received response from root node: {res.json()}')
        if res.status_code != 200:
            __logger.critical(f'Could not register node {NODE_NAME}')
            exit(1)

        # We have successfully registered the node in the root node, now register it
        # in the Zookeeper
        parent_path = res.json()['path']
        zookeeper_connector.register_node(parent_path)
        
        __logger.info(f'Node {NODE_NAME} successfully registered. The node is ready to use.')

# Disable uvicorn logging as it is not revelant for our application
logging.getLogger('uvicorn.error').disabled = True
logging.getLogger('uvicorn.access').disabled = True

# Start the uvicorn server
uvicorn.run(app, host=NODE_NAME, port=API_PORT, log_level='critical')
