from typing import Dict

import fastapi
from pydantic import BaseModel

from message import Message
from node import Node

app = fastapi.FastAPI()

# Node is injected from main
node: Node = None


@app.post("/")
def send_message(body: Dict):
    node.received_messages.put(Message(**body))


@app.post("/health")
def health():
    return {}  # Actually 200 is sufficient
