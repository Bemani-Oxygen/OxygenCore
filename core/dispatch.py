import copy
from typing import Optional, Dict, Any

from .base import Model, Base, Status
from .protocol import Node
from .data import Data
from . import DEBUG

class UnrecognizedPCBIDException(Exception):
    def __init__(self, pcbid: str, model: str, ip: str) -> None:
        self.pcbid = pcbid
        self.model = model
        self.ip = ip


class Dispatch:
    """
    Dispatch object responsible for taking a decoded tree of Node objects
    from a game, looking up config, dispatching it to the correct game
    class and then returning a response.
    """

    def __init__(self, config: Dict[str, Any], data: Data, verbose: bool) -> None:
        """
        Initialize the Dispatch object.

        Parameters:
            config - A dictionary of configuration used for various settigs.
            data - A Data singleton for DB access.
            verbose - Whether we get chatty to stdout or not.
        """
        self.__verbose = verbose
        self.__data = data
        self.__config = config

    def log(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """
        Given a message, format it and print it.

        Note that this only prints to stdout if we were initialized with
        verbose = True.

        Parameters:
            msg - A formatstring that should be formatted with any
                  optional arguments or keyword arguments.
        """
        if self.__verbose:
            print(msg.format(*args, **kwargs))

    async def handle(self, tree: Node) -> Optional[Node]:
        """
        Given a packet from a game, handle it and return a response.

        Parameters:
            tree - A Node representing the root of a tree. Expected to
                   come from an external game.

        Returns:
            A Node representing the root of a response tree, or None if
            we had a problem parsing or generating a response.
        """
        self.log("Received request:\n{}", tree)

        if tree.name != 'call':
            # Invalid request
            self.log("Invalid root node {}", tree.name)
            return None

        if len(tree.children) != 1:
            # Invalid request
            self.log("Invalid number of children for root node")
            return None

        modelstring = tree.attribute('model')
        model = Model.from_modelstring(modelstring)
        pcbid = tree.attribute('srcid')

        pcb = await self.__data.local.machine.get_machine(pcbid)

        # If we don't have a Machine, but we aren't enforcing, we must create it
        if pcb is None:
            pcb = await self.__data.local.machine.create_machine(pcbid)

        request = tree.children[0]

        config = copy.copy(self.__config)
        config['machine'] = {
            'pcbid': pcbid,
            'arcade': pcb.arcade,
        }

        # If the machine we looked up is in an arcade, override the global
        # paseli settings with the arcade paseli settings.
        if pcb.arcade is not None:
            arcade = await self.__data.local.machine.get_arcade(pcb.arcade)
            if arcade is not None:
                config['paseli']['enabled'] = arcade.data.get_bool('paseli_enabled')
                config['paseli']['infinite'] = arcade.data.get_bool('paseli_infinite')

        game = Base.create(self.__data, config, model)
        method = request.attribute('method')
        response = None

        # First, try to handle with specific service/method function
        try:
            handler = getattr(game, f'handle_{request.name}_{method}_request')
        except AttributeError:
            handler = None
        if handler is not None:
            response = await handler(request)

        if response is None:
            # Now, try to pass it off to a generic service handler
            try:
                handler = getattr(game, f'handle_{request.name}_request')
            except AttributeError:
                handler = None
            if handler is not None:
                response = await handler(request)

        if response is None:
            # Unrecognized handler
            self.log(f"Unrecognized service {request.name} method {method}")
            return None

        # Make sure we have a status value if one wasn't provided
        if 'status' not in response.attributes:
            response.set_attribute('status', str(Status.SUCCESS))

        root = Node.void('response')
        root.add_child(response)
        root.set_attribute('dstid', pcbid)

        self.log("Sending response:\n{}", root)

        return root
