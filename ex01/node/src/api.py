import threading
import time
from typing import Dict

import fastapi
import argparse
import uvicorn
import requests
from api_node import received_messages
from message import Message
from api_node import Node

REQ_INTERVAL = 1  # s

app = fastapi.FastAPI()


def build_message(body: Dict, endpoint):
    print(f"Received election message from {body['sender_id']}")
    return Message(
        key=endpoint,
        value=body['value'],
        sender=int(body['sender_id'])
    )


@app.post("/election")
def send_message(body: Dict):
    message = build_message(body, 'election')
    received_messages.put(message)


@app.get("/health")
def health():
    return {'hello': 'world'}  # 200 is sufficient


# Local development without docker for easier testing
localhost = '127.0.0.1'
local_addrs = [(localhost, 2333), (localhost, 2334)]

argparser = argparse.ArgumentParser()
argparser.add_argument('--node_addr', type=int, required=True, help='Address of this node')
args = argparser.parse_args()

node_urls = [f'http://{addr[0]}:{addr[1]}' for addr in local_addrs]
hostname = local_addrs[args.node_addr][0]
port = local_addrs[args.node_addr][1]
api_url = f'http://{hostname}:{port}'


def run_node():
    # Dumbest way to synchronize thread with the api is just to send GET request until it 
    # receives 200

    # We could also start Uvicorn from commandline and create this thread in the script but
    # its not documented
    print('Starting node thread ...')
    n_tries = 10
    while True:
        if n_tries == 0:
            print('Failed to start node, please restart the app')
            exit(1)

        time.sleep(REQ_INTERVAL)
        res = requests.get(f'{api_url}/health')  # this will block until conn is established

        if res.status_code != 200:
            print('Waiting for api to start')
            continue

        break
    print(f'Running node {args.node_addr}')
    Node(
        node_addr=node_urls[args.node_addr],
        node_addrs=node_urls
    ).run()


# Start node thread
thread = threading.Thread(target=run_node)
thread.daemon = True
thread.start()

# Run the API
uvicorn.run(app, host=hostname, port=port)
