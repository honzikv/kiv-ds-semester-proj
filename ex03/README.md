# Binary Tree distributed cache

This application is a simple implementation of distributed cache in form of binary tree (i.e. each node has up to two children).
The app is built on Vagrant and Docker. The system contains a single Zookeeper node and N cache nodes that are simple key value
stores. Each cache node is a separate Docker container that uses FastAPI to implement a REST API service and Kazoo to register in Zookeeper.

Each node exposes said API on port 5000. The API has several
endpoints:

`GET /store/{key}` - performs a lookup in the cache for the given key and returns the value if found. Returns 404 if the key is not found.

`PUT /store/{key}` - stores the given key in the cache. The value is taken from the request body (field `value`). Returns 200 if the key was stored successfully. If invoked in a node that is not the root of the tree, the request is forwarded to the root node.

`DELETE /store/{key}` - deletes the given key from the cache. Returns 200 if the key was deleted successfully. If invoked in a node that is not the root of the tree, the request is forwarded to the root node.

# The infrastructure

As previously mentioned, the nodes form a binary tree. This
tree is kept both in Zookeeper and the root node. The application does not consider any nodes to fail. Apart from
the root node, the tree is formed arbitrarily - first node
that contacts the root node is assigned as the left child,
second as the right child, etc. The root node is the only node
that is consistent in the system. After registering in the root node, each node also registers itself in the Zookeeper.

## Configuration

The application can be configured using `Vagrantfile`. We can configure following properties:

- `TREE_DEPTH` - the depth of the tree. The root node is at depth 1, its children are at depth 2, etc. The default value is 3.

- `API_PORT` - the port on which the API is exposed. The default value is 5000.

- `ROOT_NODE_ID` - specifies id of the root node. The identifiers are indexed from 1 to N, where N is the number of nodes in the system. The default value is 1.

- `STARTUP_DELAY` - specifies the delay between starting the nodes. The default value is 5 seconds.

# Running the application

To run the application, we need to have Vagrant and Docker installed. Then in the root of the project, we run:
`vagrant destroy -f && vagrant up` or `vagrant up` if it is the first time we run the application.

## Communicating with the nodes
