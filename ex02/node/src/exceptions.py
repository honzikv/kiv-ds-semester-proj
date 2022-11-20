# This module contains exceptions for more readable control flow

class ElectionUnsuccessfulException(Exception):
    pass

class ClusterResetException(Exception):
    pass

class MasterDisconnectedException(Exception):
    pass
