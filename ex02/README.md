# Exercise 02 - Single master selection in a distributed system with failure detection

This application demonstrates simple master selection in a distributed system
simulated via Vagrant and Docker.

## The algorithm

To establish the master the application uses the Bully algorithm
(see [Bully Algorithm](https://www.wikiwand.com/en/Bully_algorithm)). Nodes in the system are identical and only differ
in the ID they are (statically) assigned before the system start.


### Master selection
The algorithm for establishing the master works as follows. When a node starts, it tries to connect to other nodes in
the system via **ELECTION** request:

- Node sends requests to all nodes with higher ID
- If node receives message from a node with higher ID, it does not send anything and waits for the election to finish (it "surrenders")
- If node receives message from a node with lower ID, it sends **SURRENDER** message to the other node
- If node receives **VICTORY** message it registers the master and enters slave mode.
- If node receives no victory / surrender message before a given timeout it assumes it is the master and sends
  **VICTORY** message to other nodes.
  - Usually, this is the node with the highest ID

After the election is finished, master coordinates color change of each node in the system.

### Color change

To color the nodes, master first needs to know which nodes have survived the election. To do so it sends a **HEARTBEAT**
signal to each node which must respond with a heartbeat response. If node does not answer, it is considered dead and is not included in
the color changing procedure.

Nodes are colored like so:
 - 1/3rd of the nodes are **GREEN**, the number of green nodes is rounded up and master must always be green
 - Remainder of the nodes are colored **RED**

Similarly to the previous step, the master sends a **COLOR** message to each node. If node receives the message, it changes its
color and responds back. If the node does not respond, it is again considered dead
and the procedure fails - the master attempts to color the nodes again.


### Failure detection

To detect failures master and slave node send heartbeats to each other. If a slave node does not receive any message from master in a given timeframe it considers master dead and triggers a new election.

Similarly, master keeps information about each slave's last response. If a certain timeout is exceeded, master removes the node from the network and recolors remaining slave nodes in the network.

Finally, the network needs to allow new nodes to join. Both slave and master nodes check election messages and if there is an election triggered by new node they enter election mode as well (if necessary).

## Implementation

The application is written in Python (3.9) and uses FastAPI, requests, and Uvicorn.

Each node comprises two main components:
- Node thread that contains the implementation of the aforementioned algorithm
- FastAPI HTTP service for communication between nodes

The communication between nodes is done via HTTP requests. At the start of the application, the logic of the node is
run in a separate thread while the main thread is used to run the HTTP service. The HTTP service has endpoints for
all three main states in the node's lifecycle which are accordingly mapped to messages that the node processes (election,
color and heartbeat). 

If the API receives a message it simply forwards it to the node thread via message queue. The node periodically checks and processes message queue, depending on its current state.

## Run and deployment

Vagrant and Docker are necessary to build the application. The application is deployed using following command in the `ex02` directory:

```
vagrant up
```

This command will create the node infrastructure and start the application. 

To stop the application, run:

```
vagrant halt
```

And to remove the infrastructure, run:

```
vagrant destroy
```

Alternatively, an easy way to fully reset docker logs and log files is to run:
```
vagrant destroy -f && vagrant up
```

Which will start the application from scratch.

It is also possible to change the number of nodes in the system by changing the 
`APP_NODES_COUNT` variable in the `Vagrantfile` (at line 25).

### Output

Each node has its own log file in the `ex02` directory that is created automatically when the node runs.
This log file contains all the information logged by the node during its lifetime - alternatively, this
is also logged in the standard output of the node, accessible e.g. via Docker Desktop application.

### Example output for a 5-node system

All nodes are running:
```
(NODE-5): Starting node! 💻
(NODE-5): Current color is "init"
(NODE-5): Starting election! 🗳️
(NODE-5): Found node with lower id (NODE-2), sending surrender message...
(NODE-5): Found node with lower id (NODE-3), sending surrender message...
(NODE-5): Found node with lower id (NODE-1), sending surrender message...
(NODE-5): Found node with lower id (NODE-4), sending surrender message...
(NODE-5): Declaring self as master
(NODE-5): Changing color from "init" to "master"
(NODE-5): Setting up node colors...
(NODE-5): Changing color from "master" to "green"
(NODE-5): Node colors have been set up!
(NODE-5): NODE-1 color: red
(NODE-5): NODE-2 color: green
(NODE-5): NODE-3 color: red
(NODE-5): NODE-4 color: red
(NODE-5): NODE-5 color: green
(NODE-5): Received heartbeat from NODE-3
(NODE-5): Received heartbeat from NODE-1
(NODE-5): Received heartbeat from NODE-4
(NODE-5): Received heartbeat from NODE-2
```

NODE-5, NODE-4, NODE-3 disconnect / die -> NODE-2 becomes the master:
```
(NODE-2): Master (NODE-5) did not respond, starting an election
(NODE-2): Changing color from "green" to "init"
(NODE-2): Starting election! 🗳️
(NODE-2): Found node with lower id (NODE-1), sending surrender message...
(NODE-2): Declaring self as master
(NODE-2): Changing color from "init" to "master"
(NODE-2): Setting up node colors...
(NODE-2): Changing color from "master" to "green"
(NODE-2): Node colors have been set up!
(NODE-2): NODE-1 color: red
(NODE-2): NODE-2 color: green
(NODE-2): NODE-3 color: N/A (disconnected)
(NODE-2): NODE-4 color: N/A (disconnected)
(NODE-2): NODE-5 color: N/A (disconnected)
(NODE-2): Received heartbeat from NODE-1

```

NODE-5 restores the connection and becomes the master again:
```
(NODE-5): Starting node! 💻
(NODE-5): Current color is "init"
(NODE-5): Starting election! 🗳️
(NODE-5): Declaring self as master
(NODE-5): Changing color from "init" to "master"
(NODE-5): Setting up node colors...
(NODE-5): Found node with lower id (NODE-1), sending surrender message...
(NODE-5): Cluster reset due to new node...
(NODE-5): Changing color from "master" to "init"
(NODE-5): Starting election! 🗳️
(NODE-5): Found node with lower id (NODE-2), sending surrender message...
(NODE-5): Declaring self as master
(NODE-5): Changing color from "init" to "master"
(NODE-5): Setting up node colors...
(NODE-5): Changing color from "master" to "green"
(NODE-5): Node colors have been set up!
(NODE-5): NODE-1 color: red
(NODE-5): NODE-2 color: red
(NODE-5): NODE-3 color: N/A (disconnected)
(NODE-5): NODE-4 color: N/A (disconnected)
(NODE-5): NODE-5 color: green
(NODE-5): Received heartbeat from NODE-2
(NODE-5): Received heartbeat from NODE-1
```
