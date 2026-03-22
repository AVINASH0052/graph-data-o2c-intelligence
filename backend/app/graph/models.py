"""
Pydantic models for graph API responses.
"""
from pydantic import BaseModel
from typing import Any


class NodeModel(BaseModel):
    id: str
    label: str
    node_type: str
    community: int = 0
    attributes: dict[str, Any] = {}


class EdgeModel(BaseModel):
    source: str
    target: str
    edge_type: str


class GraphResponse(BaseModel):
    nodes: list[NodeModel]
    edges: list[EdgeModel]


class NodeDetailResponse(BaseModel):
    node: NodeModel
    neighbors: list[NodeModel]
    edges: list[EdgeModel]
