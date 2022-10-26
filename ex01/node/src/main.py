import os
from node import Node


if __name__ == '__main__':

    # Parse environment variables
    port = int(os.environ.get('PORT', 1337))
    id_limit = int(os.environ.get('ID_LIMIT', 10))
    host_name = os.environ.get('HOSTNAME')

    node = Node(
        communication_port=port,
        n_nodes=id_limit,
        hostname=host_name
    ).run()

