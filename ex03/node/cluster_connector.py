from dataclasses import dataclass
from typing import List

@dataclass
class ConnectionConfig:
    """
    Connection configuraiton
    """
    
    parent_node: str | None
    child_nodes: List[str] | None

