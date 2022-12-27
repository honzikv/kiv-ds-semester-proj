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

The application can be configured using `Vagrantfile`. We can configure following properties (starting at line 33):

- `TREE_DEPTH` - the depth of the tree. The root node is at depth 1, its children are at depth 2, etc. The default value is 3.

- `API_PORT` - the port on which the API is exposed. The default value is 5000.

- `ROOT_NODE_ID` - specifies id of the root node. The identifiers are indexed from 1 to N, where N is the number of nodes in the system. The default value is 1.

- `STARTUP_DELAY` - specifies the delay between starting the nodes. The default value is 5 seconds. Root node is never delayed.

# Running the application

To run the application, we need to have Vagrant and Docker installed. Then in the root of the project, we run:
`vagrant destroy -f && vagrant up` or `vagrant up` if it is the first time we run the application.

## Communication with the nodes via HTTP

Each node exposes its API port on the host machine depending on
its id. By default, the first node (NODE-1) starts on port 5001 - i.e. it can be accessed like so:

`curl http://localhost:5001/`

Which will give us the following json:
```
{
    "status": "alive",
    "node": "NODE-1",
    "address": "10.0.1.67"
}
```

Alternatively, we can also use ssh to connect to the Docker container and
communicate with the API via docker's network. To do so we need
to use the 10.0.1.* address space:

`vagrant ssh NODE-1`
`curl http://NODE-1:5000/`

All APIs by default run on port 5000. The CURL command will give us the same response as above.

### OpenAPI Documentation

The API is documented using OpenAPI which is exposed on the
`/docs` endpoint. For example, the documentation for the first node can be accessed here http://localhost:5001/docs.

## CLI application

Additionally, the application contains a CLI application that can be 
used to communicate with the nodes. This application can be run
in docker container or on the host machine.