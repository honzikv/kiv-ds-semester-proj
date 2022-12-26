import cluster.cluster_structure as cluster_structure

from fastapi import APIRouter

# This is only used in the root node
cluster_router = APIRouter()


@cluster_router.get('/nodes/parent/{node_name}')
def find_absolute_parent_path(node_name: str):
    return {'path': cluster_structure.find_absolute_parent_path(node_name)}


@cluster_router.get('/nodes/structure')
def get_tree():
    return {'structure': cluster_structure.get_structure()}
