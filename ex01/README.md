# Exercise 01 - Single master selection in a distributed system

This application demonstrates simple master selection in a distributed system
simulated via Vagrant and Docker.

## The algorithm

To establish the master the application uses the Bully algorithm
(see [Bully Algorithm](https://www.wikiwand.com/en/Bully_algorithm)). Nodes in the system are identical and only differ
in the ID they are (statically) assigned before the system start. Master is selected as a node with the highest ID. Here,
the algorithm is simplified since we do not have to deal with node failures, and therefore allow for multiple masters.


### Master (s)election
The algorithm for establishing the master works as follows. When a node starts, it tries to connect to other nodes in
the system via **ELECTION** request:

- If node has the highest ID it must be the master, and therefore sends **VICTORY** message to other nodes.
- Otherwise, if its ID is lower, it sends election request to nodes that have higher id
- If node receives message from a node with higher ID, it does not send anything and waits for the election to finish
- If node receives message from a node with lower ID, it sends **SURRENDER** message to the other node
- If node receives **VICTORY** message it registers the master and enters slave mode.
- If node receives no election / victory / surrender message before given timeout it assumes it is the master and sends
  **VICTORY** message to other nodes.

After the election is finished, master coordinates color change of each node in the system.

### Color change

To color the nodes, master first needs to know which nodes have survived the election. To do so it sends a **HEARTBEAT**
signal to each node which must respond accordingly. If node does not respond, it is considered dead and is not included in
the color changing procedure.

Nodes are colored like so:
 - 1/3rd of the nodes are **GREEN**, # of green nodes is rounded up and master must always be green
 - Remainder of the nodes are colored **RED**

Similarly to previous step, the master sends a **COLOR** message to each node. If node receives the message, it changes its
color to the one specified in the message and responds accordingly. If node does not respond, it is again considered dead
and the procedure fails (the master logs that some nodes could not be colored).

After the color change is finished, both the master and the slave nodes enter "working" mode where they send heartbeat
signals between them (i.e., master -> slave and slave -> master).

## Implementation

The application is written in Python (3.7+) and uses FastAPI, requests, and Uvicorn.

Each node comprises two main components:
- Node thread that contains the implementation of the aforementioned algorithm
- FastAPI HTTP service for communication between nodes

The communication between nodes is done via HTTP requests. At the start of the application, the logic of the node is
run in a separate thread while the main thread is used to run the HTTP service. The HTTP service has endpoints for
all three main states in the node's lifecycle which are accordingly mapped to messages that the node processes (election,
color and heartbeat). If the API receives a message it simply forwards it to the node thread via a queue which will
eventually read it and process it.

## Run and deployment

To run the application you will need to have Vagrant and Docker installed. The application is deployed via Vagrant
using following command in the `ex01` directory:

```
vagrant up
```

This command will create the infrastructure and start the application. 

To stop the application, run:

```
vagrant halt
```

And to remove the infrastructure, run:

```
vagrant destroy
```

It is also possible to change the number of nodes in the system by changing the 
`APP_NODES_COUNT` variable in the `Vagrantfile` (at line 25).

### Output

Each node has its own log file in the `ex01` directory that is created automatically when the node runs.
This log file contains all the information logged by the node during its lifetime - alternatively, this
is also logged in the standard output of the node, accessible e.g. via Docker Desktop application.

Example output for 3-node system:

Master node (NODE-3):
```log
NODE-3 Attempting to establish new master
NODE-3 Selected as MASTER
NODE-3 Running MASTER mode...
NODE-3 Changing color from "init" to "master"
NODE-3 Finding active nodes...
NODE-3 Found 2 active slave nodes. Assigning colors
NODE-3 Changing color from "master" to "green"
NODE-3 SUCCESS - All nodes have been colored
NODE-3 NODE-1 color: red
NODE-3 NODE-2 color: red
NODE-3 NODE-3 color: green
NODE-3 Sending heartbeat to slaves
NODE-3 Responding to heartbeat request
NODE-3 Responding to heartbeat request
...
```

Slave node (NODE-2):
```log
NODE-2 Attempting to establish new master
NODE-2 Found node with lower id, sending surrender order.
NODE-2 Master (NODE-3) has been established via victory message
NODE-2 Running SLAVE mode...
NODE-2 Changing color from "init" to "slave"
NODE-2 Changing color from "slave" to "red"
NODE-2 Sending heartbeat to master
...
```


Example output for a 6-node system looks like this, where only two nodes communicated during election:

Master node (NODE-6):
```log
NODE-6 Attempting to establish new master
NODE-6 Selected as MASTER
NODE-6 Running MASTER mode...
NODE-6 Changing color from "init" to "master"
NODE-6 Finding active nodes...
NODE-6 Found 1 active slave nodes. Assigning colors
NODE-6 Changing color from "master" to "green"
NODE-6 SUCCESS - All nodes have been colored
NODE-6 NODE-1 color: N/A (disconnected)
NODE-6 NODE-2 color: N/A (disconnected)
NODE-6 NODE-3 color: N/A (disconnected)
NODE-6 NODE-4 color: red
NODE-6 NODE-5 color: N/A (disconnected)
NODE-6 NODE-6 color: green
NODE-6 Sending heartbeat to slaves
NODE-6 Responding to heartbeat request
NODE-6 Sending heartbeat to slaves
NODE-6 Responding to heartbeat request
...
```

Slave node (NODE-4):
```
NODE-4 Attempting to establish new master
NODE-4 Master (NODE-6) has been established via victory message
NODE-4 Running SLAVE mode...
NODE-4 Changing color from "init" to "slave"
NODE-4 Changing color from "slave" to "red"
NODE-4 Sending heartbeat to master
NODE-4 Responding to heartbeat request
NODE-4 Sending heartbeat to master
...
```

