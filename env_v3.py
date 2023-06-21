from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from classv3 import VariableDef


class EnvironmentManager:
    """
    The EnvironmentManager class keeps a mapping between each variable name (aka symbol)
    in a brewin program and the VariableDef object, which stores the variable name, its type, and
    the current value that the variable is set to (which could be the same type or a subtype of
    the variable, in the case of object references).
    """

    def __init__(self) -> None:
        self.environment: list[dict[str, "VariableDef"]] = [{}]

    # returns a VariableDef object
    def get(self, symbol: str) -> Optional["VariableDef"]:
        for env in reversed(self.environment):
            if symbol in env:
                return env[symbol]
        return None

    # create a new symbol in the most nested block's environment; error if
    # the symbol already exists in the most nested block
    # this is called for all variables defined in a let block or in formal parameters
    def create_new_symbol(self, symbol: str) -> bool:
        if symbol not in self.environment[-1]:
            self.environment[-1][symbol] = None  # type:ignore
            return True
        return False

    # set works with symbols that were already created via create_new_symbol().
    # this won't create a new symbol, only update its value to a new Value object
    # returns False if the set failed due to an unknown variable that wasn't found in any
    # of the nested blocks of the current function
    def set(self, symbol: str, value: "VariableDef") -> bool:
        for env in reversed(self.environment):
            if symbol in env:
                env[symbol] = value
                return True

        return False

    # used when we enter a nested block to create a new environment for that block
    def block_nest(self) -> None:
        self.environment.append({})  # [{}] -> [{}, {}]

    # used when we exit a nested block to discard the environment for that block
    def block_unnest(self) -> None:
        self.environment.pop()
