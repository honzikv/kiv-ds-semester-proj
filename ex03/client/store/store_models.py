from typing import Any
from pydantic import BaseModel

class PutKeyRequest(BaseModel):
    key: str
    value: Any
    _wait_for_parent: bool = True