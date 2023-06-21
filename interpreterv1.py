from bparser import BParser
from copy import deepcopy
from functools import reduce
from intbase import InterpreterBase, ErrorType
from types import NoneType
from typing import Any, Optional, Type, TypeAlias, cast

################################################################################
#                               Type Definitions                               #
################################################################################

Value: TypeAlias = "NULL | bool | int | str | ObjectDefinition"
Statement: TypeAlias = str | list[Any]


class NULL:
    def __eq__(self, __value: object) -> bool:
        return isinstance(__value, NULL)


class Method:
    args: list[str]
    body: Statement

    def __init__(self, args: list[str], body: Statement) -> None:
        self.args = deepcopy(args)
        self.body = deepcopy(body)


################################################################################
#                                 Typeclasses                                  #
################################################################################


def in_eq(value: Optional[Value]) -> bool:
    return type(value) in [NULL, bool, int, str, ObjectDefinition]


def in_ord(value: Optional[Value]) -> bool:
    return type(value) in [int, str]


def in_add(value: Optional[Value]) -> bool:
    return type(value) in [int, str]


def in_num(value: Optional[Value]) -> bool:
    return type(value) in [int]


def in_bool(value: Optional[Value]) -> bool:
    return type(value) in [bool]


def in_null(value: Optional[Value]) -> bool:
    return type(value) in [NoneType, NULL]


def in_show(value: Optional[Value]) -> bool:
    return type(value) in [NoneType, bool, int, str]


################################################################################
#                               Helper Functions                               #
################################################################################


def is_string_literal(x: str) -> bool:
    return x[0] == BParser.QUOTE_CHAR and x[-1] == BParser.QUOTE_CHAR


def from_string(x: str) -> Value:
    try:
        return int(x)
    except:
        if x == InterpreterBase.NULL_DEF:
            return NULL()
        elif x == InterpreterBase.FALSE_DEF:
            return False
        elif x == InterpreterBase.TRUE_DEF:
            return True
        elif is_string_literal(x):
            return x[1:-1]
        else:
            return x


def to_string(x: Optional[Value]) -> str:
    if isinstance(x, NoneType):
        return "None"
    if isinstance(x, NULL):
        return InterpreterBase.NULL_DEF
    elif isinstance(x, bool):
        return str(x).lower()
    elif isinstance(x, int):
        return str(x)
    elif isinstance(x, ObjectDefinition):
        raise TypeError
    else:
        return x


def are_same_type(values: list[Optional[Value]]) -> bool:
    # Map NULL objects to type ObjectDefinition because they are comparable
    types: list[Type] = [
        ObjectDefinition if isinstance(value, NULL) else type(value) for value in values
    ]
    return all(map(lambda type: type == types[0], types))


# Map from class name to ClassDefinition
classes: dict[str, "ClassDefinition"] = dict()


class ClassDefinition:
    my_methods: dict[str, Method]
    my_fields: dict[str, list[Optional[Value]]]
    my_interpreter: InterpreterBase

    def __init__(self, interpreter: InterpreterBase) -> None:
        self.my_methods = dict()
        self.my_fields = dict()
        self.my_interpreter = interpreter

    def add_method(self, method_name: str, args: list[str], body: Statement) -> None:
        if method_name in self.my_methods:
            self.my_interpreter.error(ErrorType.NAME_ERROR)
        self.my_methods[method_name] = Method(args, body)

    def add_field(self, field_name: str, value: str) -> None:
        if field_name in self.my_fields:
            self.my_interpreter.error(ErrorType.NAME_ERROR)
        self.my_fields[field_name] = [from_string(value)]

    def instantiate_object(self) -> "ObjectDefinition":
        return ObjectDefinition(self.my_methods, self.my_fields, self.my_interpreter)


class ObjectDefinition:
    my_methods: dict[str, Method]
    my_fields: dict[str, list[Optional[Value]]]
    my_interpreter: InterpreterBase
    my_return: tuple[bool, Optional[Value]]

    def __init__(
        self,
        methods: dict[str, Method],
        fields: dict[str, list[Optional[Value]]],
        interpreter: InterpreterBase,
    ) -> None:
        self.my_methods = deepcopy(methods)
        self.my_fields = deepcopy(fields)
        self.my_fields[interpreter.ME_DEF] = [self]
        self.my_interpreter = interpreter
        self.my_return = (False, None)

    def __find_method(self, method_name: str) -> Method:
        if method_name not in self.my_methods:
            self.my_interpreter.error(ErrorType.NAME_ERROR)
        return self.my_methods[method_name]

    def __find_field(self, field_name: str) -> Optional[Value]:
        if field_name not in self.my_fields or self.my_fields[field_name] == []:
            self.my_interpreter.error(ErrorType.NAME_ERROR)
        return self.my_fields[field_name][-1]

    def __execute_print_statement(self, inputs: Statement) -> None:
        def accumulate(acc: str, cur: Statement) -> str:
            res: Optional[Value] = self.__run_statement(cur)
            if in_show(res):
                return acc + to_string(res)
            else:
                self.my_interpreter.error(ErrorType.TYPE_ERROR)

        self.my_interpreter.output(reduce(accumulate, inputs, ""))

    def __execute_input_integer_statement(self, name: str) -> None:
        value: int = cast(int, from_string(cast(str, self.my_interpreter.get_input())))
        if name in self.my_fields:
            self.my_fields[name].append(value)
        else:
            self.my_fields[name] = [value]

    def __execute_input_string_statement(self, name: str) -> None:
        value: str = cast(str, from_string(cast(str, self.my_interpreter.get_input())))
        if name in self.my_fields:
            self.my_fields[name].append(value)
        else:
            self.my_fields[name] = [value]

    def __execute_call_statement(
        self, target_object: Statement, method_name: str, params: Statement
    ) -> Optional[Value]:
        obj: ObjectDefinition
        if isinstance(target_object, str):
            obj = cast(ObjectDefinition, self.__find_field(target_object))
        else:
            obj = cast(ObjectDefinition, self.__run_statement(target_object))

        if in_null(obj):
            self.my_interpreter.error(ErrorType.FAULT_ERROR)

        method: Method = obj.__find_method(method_name)
        if len(method.args) != len(params):
            self.my_interpreter.error(ErrorType.TYPE_ERROR)
        # Add local variables to a stack to allow for shadowing
        for i in range(len(params)):
            if method.args[i] in obj.my_fields:
                obj.my_fields[method.args[i]].append(self.__run_statement(params[i]))
            else:
                obj.my_fields[method.args[i]] = [self.__run_statement(params[i])]
        return_value: Optional[Value] = obj.__run_statement(method.body)
        # Remove all of the local variables from the stack
        for i in range(len(params)):
            obj.my_fields[method.args[i]].pop()
        self.my_return = (False, None)
        return return_value

    def __execute_while_statement(
        self, expression: Statement, statement: Statement
    ) -> Optional[Value]:
        while True:
            value: Optional[Value] = self.__run_statement(expression)
            if not in_bool(value):
                self.my_interpreter.error(ErrorType.TYPE_ERROR)
            elif not value:
                break
            self.__run_statement(statement)
            if self.my_return[0]:
                return self.my_return[1]

    def __execute_if_statement(
        self,
        expression: Statement,
        if_true: Statement,
        if_false: Statement,
    ) -> Optional[Value]:
        value: Optional[Value] = self.__run_statement(expression)
        if not in_bool(value):
            self.my_interpreter.error(ErrorType.TYPE_ERROR)
        if value:
            self.__run_statement(if_true)
        elif if_false != []:
            self.__run_statement(if_false[0])
        if self.my_return[0]:
            return self.my_return[1]

    def __execute_return_statement(self, expression: Statement) -> Optional[Value]:
        if expression == []:
            self.my_return = (True, None)
        else:
            self.my_return = (True, self.__run_statement(expression[0]))
        return self.my_return[1]

    def __execute_begin_statement(self, statements: Statement) -> Optional[Value]:
        for statement in statements:
            self.__run_statement(statement)
            if self.my_return[0]:
                return self.my_return[1]

    def __execute_set_statement(self, var_name: str, statement: Statement) -> None:
        value: Optional[Value] = self.__run_statement(statement)
        if var_name in self.my_fields:
            self.my_fields[var_name][-1] = value
        else:
            self.my_interpreter.error(ErrorType.NAME_ERROR)

    # Interpret the specified method using the provided parameters
    def call_method(self, method_name: str, params: Statement) -> Optional[Value]:
        return self.__execute_call_statement(
            cast(Statement, InterpreterBase.ME_DEF), method_name, params
        )

    # runs/interprets the passed-in statement until completion and gets the result, if any
    def __run_statement(self, statement: Statement) -> Optional[Value]:
        match statement:
            case [InterpreterBase.PRINT_DEF, *inputs]:
                self.__execute_print_statement(inputs)
            case [InterpreterBase.INPUT_INT_DEF, var_name]:
                self.__execute_input_integer_statement(var_name)
            case [InterpreterBase.INPUT_STRING_DEF, var_name]:
                self.__execute_input_string_statement(var_name)
            case [InterpreterBase.SET_DEF, var_name, statement]:
                self.__execute_set_statement(var_name, statement)
            case [InterpreterBase.WHILE_DEF, expression, statement]:
                return self.__execute_while_statement(expression, statement)
            case [InterpreterBase.IF_DEF, expression, if_true, *if_false]:
                return self.__execute_if_statement(expression, if_true, if_false)
            case [InterpreterBase.BEGIN_DEF, *statements]:
                return self.__execute_begin_statement(statements)
            case [InterpreterBase.RETURN_DEF, *expression]:
                return self.__execute_return_statement(expression)
            case [InterpreterBase.CALL_DEF, target_object_name, method_name, *params]:
                return self.__execute_call_statement(
                    target_object_name, method_name, params
                )
            case [InterpreterBase.NEW_DEF, class_name]:
                if class_name in classes:
                    return classes[class_name].instantiate_object()
                else:
                    self.my_interpreter.error(ErrorType.TYPE_ERROR)
            case ["+", expression1, expression2]:
                v1: Optional[Value] = self.__run_statement(expression1)
                v2: Optional[Value] = self.__run_statement(expression2)
                if are_same_type([v1, v2]) and in_add(v1):
                    return v1 + v2  # type:ignore
                else:
                    self.my_interpreter.error(ErrorType.TYPE_ERROR)
            case ["-", expression1, expression2]:
                v1: Optional[Value] = self.__run_statement(expression1)
                v2: Optional[Value] = self.__run_statement(expression2)
                if are_same_type([v1, v2]) and in_num(v1):
                    return v1 - v2  # type:ignore
                else:
                    self.my_interpreter.error(ErrorType.TYPE_ERROR)
            case ["*", expression1, expression2]:
                v1: Optional[Value] = self.__run_statement(expression1)
                v2: Optional[Value] = self.__run_statement(expression2)
                if are_same_type([v1, v2]) and in_num(v1):
                    return v1 * v2  # type:ignore
                else:
                    self.my_interpreter.error(ErrorType.TYPE_ERROR)
            case ["/", expression1, expression2]:
                v1: Optional[Value] = self.__run_statement(expression1)
                v2: Optional[Value] = self.__run_statement(expression2)
                if are_same_type([v1, v2]) and in_num(v1):
                    return v1 // v2  # type:ignore
                else:
                    self.my_interpreter.error(ErrorType.TYPE_ERROR)
            case ["%", expression1, expression2]:
                v1: Optional[Value] = self.__run_statement(expression1)
                v2: Optional[Value] = self.__run_statement(expression2)
                if are_same_type([v1, v2]) and in_num(v1):
                    return v1 % v2  # type:ignore
                else:
                    self.my_interpreter.error(ErrorType.TYPE_ERROR)
            case ["&", expression1, expression2]:
                v1: Optional[Value] = self.__run_statement(expression1)
                v2: Optional[Value] = self.__run_statement(expression2)
                if are_same_type([v1, v2]) and in_bool(v1):
                    return v1 and v2  # type:ignore
                else:
                    self.my_interpreter.error(ErrorType.TYPE_ERROR)
            case ["|", expression1, expression2]:
                v1: Optional[Value] = self.__run_statement(expression1)
                v2: Optional[Value] = self.__run_statement(expression2)
                if are_same_type([v1, v2]) and in_bool(v1):
                    return v1 or v2  # type:ignore
                else:
                    self.my_interpreter.error(ErrorType.TYPE_ERROR)
            case ["!", expression]:
                value: Optional[Value] = self.__run_statement(expression)
                if in_bool(value):
                    return not value
                else:
                    self.my_interpreter.error(ErrorType.TYPE_ERROR)
            case ["==", expression1, expression2]:
                v1: Optional[Value] = self.__run_statement(expression1)
                v2: Optional[Value] = self.__run_statement(expression2)
                if are_same_type([v1, v2]) and in_eq(v1):
                    return v1 == v2  # type:ignore
                else:
                    self.my_interpreter.error(ErrorType.TYPE_ERROR)
            case ["!=", expression1, expression2]:
                v1: Optional[Value] = self.__run_statement(expression1)
                v2: Optional[Value] = self.__run_statement(expression2)
                if are_same_type([v1, v2]) and in_eq(v1):
                    return v1 != v2  # type:ignore
                else:
                    self.my_interpreter.error(ErrorType.TYPE_ERROR)
            case ["<", expression1, expression2]:
                v1: Optional[Value] = self.__run_statement(expression1)
                v2: Optional[Value] = self.__run_statement(expression2)
                if are_same_type([v1, v2]) and in_ord(v1):
                    return v1 < v2  # type:ignore
                else:
                    self.my_interpreter.error(ErrorType.TYPE_ERROR)
            case ["<=", expression1, expression2]:
                v1: Optional[Value] = self.__run_statement(expression1)
                v2: Optional[Value] = self.__run_statement(expression2)
                if are_same_type([v1, v2]) and in_ord(v1):
                    return v1 <= v2  # type:ignore
                else:
                    self.my_interpreter.error(ErrorType.TYPE_ERROR)
            case [">", expression1, expression2]:
                v1: Optional[Value] = self.__run_statement(expression1)
                v2: Optional[Value] = self.__run_statement(expression2)
                if are_same_type([v1, v2]) and in_ord(v1):
                    return v1 > v2  # type:ignore
                else:
                    self.my_interpreter.error(ErrorType.TYPE_ERROR)
            case [">=", expression1, expression2]:
                v1: Optional[Value] = self.__run_statement(expression1)
                v2: Optional[Value] = self.__run_statement(expression2)
                if are_same_type([v1, v2]) and in_ord(v1):
                    return v1 >= v2  # type:ignore
                else:
                    self.my_interpreter.error(ErrorType.TYPE_ERROR)
            case s if isinstance(s, str):
                if is_string_literal(s):
                    return from_string(s)
                val: Value = from_string(s)
                if isinstance(val, str):
                    return self.__find_field(val)
                else:
                    return val
            case _:
                self.my_interpreter.error(ErrorType.TYPE_ERROR)


class Interpreter(InterpreterBase):
    def __init__(self, console_output=True, inp=None, trace_output=False) -> None:
        super().__init__(console_output, inp)

    def setup_class(self, parsed_class) -> None:
        if parsed_class[1] in classes:
            self.error(ErrorType.TYPE_ERROR)
        my_class = ClassDefinition(self)

        for attribute in parsed_class[2:]:
            match attribute:
                case [InterpreterBase.METHOD_DEF, method_name, args, body]:
                    my_class.add_method(method_name, args, body)
                case [InterpreterBase.FIELD_DEF, name, value]:
                    my_class.add_field(name, value)

        classes[parsed_class[1]] = my_class

    def setup(self, parsed_program) -> None:
        for parsed_class in parsed_program:
            self.setup_class(parsed_class)

    def get_main_class(self) -> ClassDefinition:
        if InterpreterBase.MAIN_CLASS_DEF not in classes:
            self.error(ErrorType.NAME_ERROR)
        return classes[InterpreterBase.MAIN_CLASS_DEF]

    def run(self, program_source: list[str]) -> None:
        classes.clear()
        result, parsed_program = BParser.parse(program_source)
        if not result:
            print(parsed_program)
            return
        # Store everything in our data structures
        self.setup(parsed_program)
        # Start execution
        main_class = self.get_main_class()
        main_object = main_class.instantiate_object()
        main_object.call_method(InterpreterBase.MAIN_FUNC_DEF, [])
