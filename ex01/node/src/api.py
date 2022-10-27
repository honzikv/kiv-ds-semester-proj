import threading
from typing import Dict

import fastapi
import argparse
import uvicorn
from api_node import received_messages
from message import Message
from api_node import Node

app = fastapi.FastAPI()


def build_message(body: Dict, endpoint):
    print(f"Received election message from {body['sender_id']}")
    message = Message(
        key='election',
        value=body['value'],
        sender=int(body['sender_id'])
    )


@app.post("/election")
def send_message(body: Dict):
    message = build_message(body, 'election')
    received_messages.put(message)


@app.post("/health")
def health():
    return {}  # 200 is sufficient


# Local development without docker for easier testing
localhost = '127.0.0.1'
local_addrs = [(localhost, 2333), (localhost, 2334)]

argparser = argparse.ArgumentParser()
argparser.add_argument('--node_addr', type=int, required=True, help='Address of this node')
args = argparser.parse_args()

def run_node():
    Node(
        node_addr=local_addrs[args.node_addr],
        node_addrs=local_addrs
    ).run()

uvicorn.run(app, host=local_addrs[args.node_addr][0], port=local_addrs[args.node_addr][1])
print('bla')
thread = threading.Thread(target=run_node)
thread.daemon = True
thread.start()
