import logging
import threading
import time
from typing import Dict

import fastapi
import argparse
import uvicorn
import os
import requests
from api_node import received_messages
from message import Message
from api_node import Node

REQ_INTERVAL = 1  # s

app = fastapi.FastAPI()


# TODO docker + vagrant + fix stdout + readme

def build_message(body: Dict, endpoint):
    return Message(
        key=endpoint,
        value=body['value'],
        sender=int(body['sender_id'])
    )


@app.post("/election")
def send_message(body: Dict):
    message = build_message(body, 'election')
    received_messages.put(message)


@app.post('/heartbeat')
def heartbeat(body: Dict):
    message = build_message(body, 'heartbeat')
    received_messages.put(message)


@app.post('/color')
def color(body: Dict):
    message = build_message(body, 'color')
    received_messages.put(message)


@app.get("/healthcheck")
def health():
    return {'hello': 'world'}  # 200 is sufficient


api_logger = logging.getLogger('Node-Start')
api_logger.setLevel(logging.INFO)


def main():
    def get_env_var(key):
        value = os.getenv(key)
        if value is None:
            raise ValueError(f'Environment variable {key} not set')
        return value

    def extract_node_addresses(env_key='node_addrs'):
        """
        Extracts node addresses from environment variable with given key.
        Node addresses must be separated by a comma.
        """
        return get_env_var(env_key).split(',')

    if os.getenv('docker') is None:
        # Local development without docker for testing purposes
        localhost = '127.0.0.1'
        local_addrs = [(localhost, 2333), (localhost, 2334), (localhost, 2335)]

        argparser = argparse.ArgumentParser()
        # This is index to the array - i.e. 0 or 1, etc.
        argparser.add_argument('--node_addr', type=int, required=True, help='Address of this node')
        args = argparser.parse_args()

        node_addr_idx = args.node_addr
        node_urls = [f'{addr[0]}:{addr[1]}' for addr in local_addrs]
        hostname = local_addrs[args.node_addr][0]
        port = local_addrs[args.node_addr][1]
        api_url = f'http://{hostname}:{port}'
    else:
        print('Detected docker run...')
        node_addr_idx = int(get_env_var('node_idx'))
        node_urls = extract_node_addresses()
        node_url = node_urls[node_addr_idx]
        split = node_url.split(':')
        hostname, port = split[0], int(split[1])
        api_url = f'http://{hostname}:{port}'

    def run_node():
        # Easiest way to synchronize the API and thread itself is to use a "health check endpoint" that we try
        # reaching until we get a 200 response
        # This would not be optimal for a real production system but will suffice for this
        n_tries = 10
        while True:
            if n_tries == 0:
                print('Failed to start node, please restart the app')
                exit(1)

            time.sleep(REQ_INTERVAL)
            api_logger.info('Trying to reach API...')
            res = requests.get(f'{api_url}/healthcheck')  # this will block until conn is established
            if res.status_code != 200:
                n_tries -= 1
                continue

            api_logger.info('Connection with API established ... starting node')
            break
        Node(
            node_addr=api_url,
            node_addrs=['http://' + url for url in node_urls],
        ).run()

    # Start node thread
    thread = threading.Thread(target=run_node)
    thread.daemon = True
    thread.start()

    # Disable uvicorn logging for readability
    uvicorn_error = logging.getLogger("uvicorn.error")
    uvicorn_error.disabled = True
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.disabled = True
    uvicorn.run(app, host=hostname, port=port, log_level='critical')


if __name__ == '__main__':
    main()
