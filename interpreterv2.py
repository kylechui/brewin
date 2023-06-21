from bparser import BParser
from copy import deepcopy
from functools import reduce
from intbase import InterpreterBase, ErrorType
from typing import Any, Optional, TypeAlias, cast

################################################################################
#                               Type Definitions                               #
################################################################################

Value: TypeAlias = tuple[str, "bool | int | str | ObjectDefinition"]
Statement: TypeAlias = str | list[Any]
VOID = (InterpreterBase.VOID_DEF, 0)


class Method:
    __return_type: str
    __params: list[tuple[str, str]]
    __body: Statement

    def __init__(
        self,
        return_type: str,
        params: list[tuple[str, str]],
        body: Statement,
    ) -> None:
        self.__return_type = return_type
        self.__params = deepcopy(params)
        self.__body = deepcopy(body)

    def matches_signature(self, params: list[Value]) -> bool:
        if len(self.__params) != len(params):
            return False
        for (t, _), v in zip(self.__params, params):
            if not is_subtype(get_type(v), t):
                return False
        return True

    def get_return_type(self) -> str:
        return self.__return_type

    def get_params(self) -> list[tuple[str, str]]:
        return self.__params

    def get_body(self) -> Statement:
        return self.__body


class SymbolTable:
    __interpreter: InterpreterBase
    __variables: dict[str, list[Value]]
    __methods: dict[str, Method]

    def show(self) -> None:
        print("VARIABLES: ", self.__variables)
        print("METHODS: ", self.__methods)

    def __init__(self, interpreter: InterpreterBase) -> None:
        self.__interpreter = interpreter
        self.__variables = dict()
        self.__methods = dict()

    def add_field(self, f_name: str, f_value: Value) -> None:
        if f_name in self.__variables:
            self.__interpreter.error(ErrorType.NAME_ERROR)
        self.__variables[f_name] = [f_value]

    def add_variable(self, v_name: str, v_value: Value) -> None:
        if v_name in self.__variables:
            self.__variables[v_name].append(v_value)
        else:
            self.__variables[v_name] = [v_value]

    def add_method(
        self,
        m_name: str,
        m_return: str,
        m_params: list[tuple[str, str]],
        m_body: Statement,
    ) -> None:
        param_names: list[str] = [name for (_, name) in m_params]
        if m_name in self.__methods or not distinct(param_names):
            self.__interpreter.error(ErrorType.NAME_ERROR)
        for (t, _) in m_params:
            if not is_primitive(t) and t not in class_names:
                self.__interpreter.error(ErrorType.TYPE_ERROR)
        self.__methods[m_name] = Method(m_return, m_params, m_body)

    def get_variable(self, v_name: str) -> Optional[Value]:
        if v_name not in self.__variables or self.__variables[v_name] == []:
            return None
        return self.__variables[v_name][-1]

    def get_method(self, m_name: str, m_params: list[Value]) -> Optional[Method]:
        if m_name not in self.__methods or not self.__methods[m_name].matches_signature(
            m_params
        ):
            return None
        return self.__methods[m_name]

    def remove_variable(self, v_name: str) -> None:
        self.__variables[v_name].pop()

    def set_variable(self, v_name: str, v_value: Value) -> None:
        if v_name not in self.__variables:
            self.__interpreter.error(ErrorType.NAME_ERROR)
        self.__variables[v_name][-1] = v_value


################################################################################
#                                 Typeclasses                                  #
################################################################################


def in_eq(value: Value) -> bool:
    return value[0] not in [InterpreterBase.VOID_DEF]


def in_ord(value: Value) -> bool:
    return value[0] in [InterpreterBase.INT_DEF, InterpreterBase.STRING_DEF]


def in_add(value: Value) -> bool:
    return value[0] in [InterpreterBase.INT_DEF, InterpreterBase.STRING_DEF]


def in_num(value: Value) -> bool:
    return value[0] in [InterpreterBase.INT_DEF]


def in_bool(value: Value) -> bool:
    return value[0] in [InterpreterBase.BOOL_DEF]


def in_null(value: Value) -> bool:
    return (
        value[0] in [InterpreterBase.VOID_DEF, InterpreterBase.NULL_DEF]
        or isinstance(value[1], ObjectDefinition)
        and value[1].get_class_name() == InterpreterBase.NULL_DEF
    )


def in_show(value: Value) -> bool:
    return value[0] in [
        InterpreterBase.NULL_DEF,
        InterpreterBase.BOOL_DEF,
        InterpreterBase.INT_DEF,
        InterpreterBase.STRING_DEF,
    ]


################################################################################
#                                   Helpers                                    #
################################################################################

# Map from class name to ClassDefinition
classes: dict[str, "ClassDefinition"] = dict()
# Map from derived classes to base classes
inheritance: dict[str, str] = dict()
class_names: set[str] = set()


def distinct(lst: list) -> bool:
    return len(lst) == len(set(lst))


def is_string_literal(x: str) -> bool:
    return x[0] == BParser.QUOTE_CHAR and x[-1] == BParser.QUOTE_CHAR


def from_string(x: str) -> Value:
    if x == InterpreterBase.VOID_DEF:
        return VOID
    elif x == InterpreterBase.NULL_DEF:
        return (
            InterpreterBase.NULL_DEF,
            classes[InterpreterBase.NULL_DEF].instantiate_object(),
        )
    elif x == InterpreterBase.FALSE_DEF:
        return (InterpreterBase.BOOL_DEF, False)
    elif x == InterpreterBase.TRUE_DEF:
        return (InterpreterBase.BOOL_DEF, True)
    elif is_string_literal(x):
        return (InterpreterBase.STRING_DEF, x[1:-1])
    else:
        try:
            return (InterpreterBase.INT_DEF, int(x))
        except:
            return x  # type:ignore


def to_string(x: Value) -> str:
    t: str = x[0]
    if t == InterpreterBase.VOID_DEF:
        return InterpreterBase.VOID_DEF
    elif t == InterpreterBase.NULL_DEF:
        return InterpreterBase.NULL_DEF
    elif t == InterpreterBase.BOOL_DEF:
        return InterpreterBase.TRUE_DEF if x[1] else InterpreterBase.FALSE_DEF
    elif t == InterpreterBase.INT_DEF:
        return str(x[1])
    elif isinstance(x[1], ObjectDefinition):
        return x[1].get_class_name()
    else:
        return cast(str, x[1])


def get_type(x: Value) -> str:
    return x[0]


def is_subtype(s: str, t: str) -> bool:
    if t == InterpreterBase.VOID_DEF:
        return False
    if s == InterpreterBase.NULL_DEF and not is_primitive(t) or s == t:
        return True
    if s in inheritance:
        return is_subtype(inheritance[s], t)
    return False


def are_same_type(values: list[Value]) -> bool:  # TODO: Rename this :skull:
    types: list[str] = [get_type(value) for value in values]
    for target in types:
        if all(map(lambda t: is_subtype(t, target), types)):
            return True
    return False


def get_default(t: str) -> Value:
    if t == InterpreterBase.VOID_DEF:
        return VOID
    elif t == InterpreterBase.INT_DEF:
        return (InterpreterBase.INT_DEF, 0)
    elif t == InterpreterBase.BOOL_DEF:
        return (InterpreterBase.BOOL_DEF, False)
    elif t == InterpreterBase.STRING_DEF:
        return (InterpreterBase.STRING_DEF, "")
    else:
        return (
            InterpreterBase.NULL_DEF,
            classes[InterpreterBase.NULL_DEF].instantiate_object(),
        )


def is_primitive(t: str) -> bool:
    return t in [
        InterpreterBase.BOOL_DEF,
        InterpreterBase.INT_DEF,
        InterpreterBase.STRING_DEF,
    ]


# TODO: Remove the interpreter requirement and handle all of this directly in SymbolTable?
def upcast(t: str, v: Value, interpreter: InterpreterBase) -> Value:
    if not is_subtype(get_type(v), t):
        # print(f"Could not upcast type: {v} into type: {t}")
        interpreter.error(ErrorType.TYPE_ERROR)
    return (t, v[1])


class ClassDefinition:
    __interpreter: InterpreterBase
    __name: str
    __symbols: list[SymbolTable]

    def __init__(self, interpreter: InterpreterBase, name: str) -> None:
        self.__interpreter = interpreter
        self.__name = name
        if name in inheritance:
            self.__symbols = classes[inheritance[name]].get_symbols()
        else:
            self.__symbols = []
        self.__symbols.append(SymbolTable(interpreter))

    def add_field(self, f_type: str, f_name: str, f_value: str) -> None:
        value: Value = from_string(f_value)
        self.__symbols[-1].add_field(f_name, upcast(f_type, value, self.__interpreter))

    def add_method(
        self,
        m_name: str,
        m_return: str,
        m_params: list[tuple[str, str]],
        m_body: Statement,
    ) -> None:
        self.__symbols[-1].add_method(m_name, m_return, m_params, m_body)

    def get_symbols(self) -> list[SymbolTable]:
        return self.__symbols

    def instantiate_object(self) -> "ObjectDefinition":
        return ObjectDefinition(self.__interpreter, self.__name, self.__symbols)


class ObjectDefinition:
    __interpreter: InterpreterBase
    __class_name: str
    __symbols: list[SymbolTable]
    __active_index: int
    __return_value: tuple[bool, Value]

    def show(self) -> None:
        for symbol_table in self.__symbols[::-1]:
            symbol_table.show()

    def __init__(
        self, interpreter: InterpreterBase, class_name: str, symbols: list[SymbolTable]
    ) -> None:
        self.__interpreter = interpreter
        self.__class_name = class_name
        self.__symbols = deepcopy(symbols)
        self.__active_index = len(self.__symbols) - 1
        self.__return_value = (False, VOID)

    def __eq__(self, other: object):
        return (
            self.__class_name == self.__interpreter.NULL_DEF
            and isinstance(other, ObjectDefinition)
            and other.get_class_name() == self.__interpreter.NULL_DEF
        ) or (self is other)

    def __find_method(
        self, m_name: str, m_params: list[Value], is_super: bool
    ) -> Method:
        visible: int = self.__active_index if is_super else len(self.__symbols) - 1
        for i in range(visible, -1, -1):
            method: Optional[Method] = self.__symbols[i].get_method(m_name, m_params)
            if method is not None:
                self.__active_index = i
                return method
        self.__interpreter.error(ErrorType.NAME_ERROR)

    def __find_variable(self, v_name: str) -> Value:
        active_symbol: SymbolTable = self.get_active_symbol_table()
        variable: Optional[Value] = active_symbol.get_variable(v_name)
        if variable is not None:
            return variable
        self.__interpreter.error(ErrorType.NAME_ERROR)

    def __execute_print_statement(self, inputs: Statement) -> None:
        def accumulate(acc: str, cur: Statement) -> str:
            res: Value = self.__run_statement(cur)
            if in_show(res):
                return acc + to_string(res)
            self.__interpreter.error(ErrorType.TYPE_ERROR)

        self.__interpreter.output(reduce(accumulate, inputs, ""))

    def __execute_input_integer_statement(self, name: str) -> None:
        value: Value = from_string(cast(str, self.__interpreter.get_input()))
        active_symbol: SymbolTable = self.get_active_symbol_table()
        active_symbol.set_variable(
            name, upcast(InterpreterBase.INT_DEF, value, self.__interpreter)
        )

    def __execute_input_string_statement(self, name: str) -> None:
        value: Value = (
            InterpreterBase.STRING_DEF,
            cast(str, self.__interpreter.get_input()),
        )
        active_symbol: SymbolTable = self.get_active_symbol_table()
        active_symbol.set_variable(
            name, upcast(InterpreterBase.STRING_DEF, value, self.__interpreter)
        )

    def __execute_call_statement(
        self, target_object: Statement, m_name: str, m_params: Statement
    ) -> Value:
        m_values: list[Value] = [self.__run_statement(p) for p in m_params]
        is_super: bool = target_object == InterpreterBase.SUPER_DEF
        if is_super:
            obj: ObjectDefinition = self
        else:
            val: Value = self.__run_statement(target_object)
            if in_null(val):
                self.__interpreter.error(ErrorType.FAULT_ERROR)
            obj: ObjectDefinition = cast(ObjectDefinition, val[1])
        if is_super:
            obj.decrement_index()

        method = obj.__find_method(m_name, m_values, is_super)
        # Add local variables to a stack to allow for shadowing
        for i in range(len(m_params)):
            param_type: str = method.get_params()[i][0]
            param_name: str = method.get_params()[i][1]
            obj.get_active_symbol_table().add_variable(
                param_name, upcast(param_type, m_values[i], self.__interpreter)
            )

        return_value: Value = obj.__run_statement(method.get_body())
        obj.__return_value = (False, VOID)
        if is_super:
            obj.increment_index()

        if return_value == VOID:
            return get_default(method.get_return_type())
        return upcast(method.get_return_type(), return_value, self.__interpreter)

    def __execute_while_statement(
        self, expression: Statement, statement: Statement
    ) -> Value:
        while True:
            value: Value = self.__run_statement(expression)
            if not in_bool(value):
                self.__interpreter.error(ErrorType.TYPE_ERROR)
            elif not value[1]:
                break
            self.__run_statement(statement)
            if self.__return_value[0]:
                return self.__return_value[1]
        return VOID

    def __execute_if_statement(
        self,
        expression: Statement,
        if_true: Statement,
        if_false: Statement,
    ) -> Value:
        value: Value = self.__run_statement(expression)
        if not in_bool(value):
            self.__interpreter.error(ErrorType.TYPE_ERROR)
        elif value[1]:
            self.__run_statement(if_true)
        elif if_false != []:
            self.__run_statement(if_false[0])
        if self.__return_value[0]:
            return self.__return_value[1]
        return VOID

    def __execute_return_statement(self, expression: Statement) -> Value:
        if expression == []:
            self.__return_value = (True, VOID)
        else:
            self.__return_value = (True, self.__run_statement(expression[0]))
        return self.__return_value[1]

    def __execute_begin_statement(self, statements: Statement) -> Value:
        for statement in statements:
            self.__run_statement(statement)
            if self.__return_value[0]:
                return self.__return_value[1]
        return VOID

    def __execute_let_statement(
        self, variables: list[list[str]], statements: Statement
    ) -> Value:
        var_names: list[str] = [variable[1] for variable in variables]
        if not distinct(var_names):
            self.__interpreter.error(ErrorType.NAME_ERROR)

        for variable in variables:
            var_type: str = variable[0]
            var_name: str = variable[1]
            var_value: Value = from_string(variable[2])
            if not is_primitive(var_type) and var_type not in classes:
                self.__interpreter.error(ErrorType.TYPE_ERROR)
            active_symbol: SymbolTable = self.get_active_symbol_table()
            active_symbol.add_variable(
                var_name, upcast(var_type, var_value, self.__interpreter)
            )

        for statement in statements:
            if not self.__return_value[0]:
                self.__run_statement(statement)

        for variable in variables:
            var_name: str = variable[1]
            active_symbol: SymbolTable = self.get_active_symbol_table()
            active_symbol.remove_variable(var_name)

        if self.__return_value[0]:
            return self.__return_value[1]
        return VOID

    def __execute_set_statement(self, v_name: str, statement: Statement) -> None:
        active_symbol: SymbolTable = self.get_active_symbol_table()
        cur_value: Optional[Value] = active_symbol.get_variable(v_name)
        new_value: Value = self.__run_statement(statement)
        if cur_value is None:
            self.__interpreter.error(ErrorType.NAME_ERROR)
        elif not is_subtype(get_type(new_value), get_type(cur_value)):
            self.__interpreter.error(ErrorType.TYPE_ERROR)
        active_symbol.set_variable(v_name, new_value)

    def get_class_name(self) -> str:
        return self.__class_name

    def get_active_symbol_table(self) -> SymbolTable:
        return self.__symbols[self.__active_index]

    def increment_index(self) -> None:
        self.__active_index += 1

    def decrement_index(self) -> None:
        self.__active_index -= 1
        if self.__active_index < 0:
            self.__interpreter.error(ErrorType.TYPE_ERROR)

    # Interpret the specified method using the provided parameters
    def call_method(self, method_name: str, params: Statement) -> Value:
        return self.__execute_call_statement(
            InterpreterBase.ME_DEF, method_name, params
        )

    # runs/interprets the passed-in statement until completion and gets the result, if any
    def __run_statement(self, statement: Statement) -> Value:
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
            case [InterpreterBase.LET_DEF, variables, *statements]:
                return self.__execute_let_statement(variables, statements)
            case [InterpreterBase.RETURN_DEF, *expression]:
                return self.__execute_return_statement(expression)
            case [InterpreterBase.CALL_DEF, target_object_name, method_name, *params]:
                return self.__execute_call_statement(
                    target_object_name, method_name, params
                )
            case [InterpreterBase.NEW_DEF, class_name]:
                if class_name in classes:
                    return (class_name, classes[class_name].instantiate_object())
                else:
                    self.__interpreter.error(ErrorType.TYPE_ERROR)
            case ["+", expression1, expression2]:
                v1: Value = self.__run_statement(expression1)
                v2: Value = self.__run_statement(expression2)
                if are_same_type([v1, v2]) and in_add(v1):
                    return (v1[0], v1[1] + v2[1])  # type:ignore
                else:
                    self.__interpreter.error(ErrorType.TYPE_ERROR)
            case ["-", expression1, expression2]:
                v1: Value = self.__run_statement(expression1)
                v2: Value = self.__run_statement(expression2)
                if in_num(v1) and in_num(v2):
                    return (
                        InterpreterBase.INT_DEF,
                        cast(int, v1[1]) - cast(int, v2[1]),
                    )
                else:
                    self.__interpreter.error(ErrorType.TYPE_ERROR)
            case ["*", expression1, expression2]:
                v1: Value = self.__run_statement(expression1)
                v2: Value = self.__run_statement(expression2)
                if in_num(v1) and in_num(v2):
                    return (
                        InterpreterBase.INT_DEF,
                        cast(int, v1[1]) * cast(int, v2[1]),
                    )
                else:
                    self.__interpreter.error(ErrorType.TYPE_ERROR)
            case ["/", expression1, expression2]:
                v1: Value = self.__run_statement(expression1)
                v2: Value = self.__run_statement(expression2)
                if in_num(v1) and in_num(v2):
                    return (
                        InterpreterBase.INT_DEF,
                        cast(int, v1[1]) // cast(int, v2[1]),
                    )
                else:
                    self.__interpreter.error(ErrorType.TYPE_ERROR)
            case ["%", expression1, expression2]:
                v1: Value = self.__run_statement(expression1)
                v2: Value = self.__run_statement(expression2)
                if in_num(v1) and in_num(v2):
                    return (
                        InterpreterBase.INT_DEF,
                        cast(int, v1[1]) % cast(int, v2[1]),
                    )
                else:
                    self.__interpreter.error(ErrorType.TYPE_ERROR)
            case ["&", expression1, expression2]:
                v1: Value = self.__run_statement(expression1)
                v2: Value = self.__run_statement(expression2)
                if in_bool(v1) and in_bool(v2):
                    return (InterpreterBase.BOOL_DEF, v1[1] and v2[1])
                else:
                    self.__interpreter.error(ErrorType.TYPE_ERROR)
            case ["|", expression1, expression2]:
                v1: Value = self.__run_statement(expression1)
                v2: Value = self.__run_statement(expression2)
                if in_bool(v1) and in_bool(v2):
                    return (InterpreterBase.BOOL_DEF, v1[1] or v2[1])
                else:
                    self.__interpreter.error(ErrorType.TYPE_ERROR)
            case ["!", expression]:
                value: Value = self.__run_statement(expression)
                if in_bool(value):
                    return (InterpreterBase.BOOL_DEF, not value[1])
                else:
                    self.__interpreter.error(ErrorType.TYPE_ERROR)
            case ["==", expression1, expression2]:
                v1: Value = self.__run_statement(expression1)
                v2: Value = self.__run_statement(expression2)
                if is_subtype(v1[0], v2[0]) or is_subtype(v2[0], v1[0]):
                    return (InterpreterBase.BOOL_DEF, v1[1] == v2[1])
                else:
                    self.__interpreter.error(ErrorType.TYPE_ERROR)
            case ["!=", expression1, expression2]:
                v1: Value = self.__run_statement(expression1)
                v2: Value = self.__run_statement(expression2)
                if is_subtype(v1[0], v2[0]) or is_subtype(v2[0], v1[0]):
                    return (InterpreterBase.BOOL_DEF, v1[1] != v2[1])
                else:
                    self.__interpreter.error(ErrorType.TYPE_ERROR)
            case ["<", expression1, expression2]:
                v1: Value = self.__run_statement(expression1)
                v2: Value = self.__run_statement(expression2)
                if are_same_type([v1, v2]) and in_ord(v1):
                    return (InterpreterBase.BOOL_DEF, v1[1] < v2[1])  # type:ignore
                else:
                    self.__interpreter.error(ErrorType.TYPE_ERROR)
            case ["<=", expression1, expression2]:
                v1: Value = self.__run_statement(expression1)
                v2: Value = self.__run_statement(expression2)
                if are_same_type([v1, v2]) and in_ord(v1):
                    return (InterpreterBase.BOOL_DEF, v1[1] <= v2[1])  # type:ignore
                else:
                    self.__interpreter.error(ErrorType.TYPE_ERROR)
            case [">", expression1, expression2]:
                v1: Value = self.__run_statement(expression1)
                v2: Value = self.__run_statement(expression2)
                if are_same_type([v1, v2]) and in_ord(v1):
                    return (InterpreterBase.BOOL_DEF, v1[1] > v2[1])  # type:ignore
                else:
                    self.__interpreter.error(ErrorType.TYPE_ERROR)
            case [">=", expression1, expression2]:
                v1: Value = self.__run_statement(expression1)
                v2: Value = self.__run_statement(expression2)
                if are_same_type([v1, v2]) and in_ord(v1):
                    return (InterpreterBase.BOOL_DEF, v1[1] >= v2[1])  # type:ignore
                else:
                    self.__interpreter.error(ErrorType.TYPE_ERROR)
            case s if isinstance(s, str):
                if is_string_literal(s):
                    return from_string(s)
                val: Value = from_string(s)
                if isinstance(val, str):
                    if val == InterpreterBase.ME_DEF:
                        return (self.__class_name, self)
                    return self.__find_variable(val)
                return val
            case x:
                print("UNMATCHED: ", x)
                return x  # type:ignore
        return VOID


class Interpreter(InterpreterBase):
    def __init__(self, console_output=True, inp=None, trace_output=False) -> None:
        super().__init__(console_output, inp)

    def setup_inheritance(self, parsed_program) -> None:
        for parsed_class in parsed_program:
            match parsed_class:
                case [self.CLASS_DEF, derived_name, self.INHERITS_DEF, base_name, *_]:
                    if base_name not in class_names or derived_name in class_names:
                        self.error(ErrorType.TYPE_ERROR)
                    inheritance[derived_name] = base_name
                    class_names.add(derived_name)
                case [self.CLASS_DEF, class_name, *_]:
                    if class_name in class_names:
                        self.error(ErrorType.TYPE_ERROR)
                    class_names.add(class_name)

    def setup_class(self, parsed_class) -> None:
        class_name: str = parsed_class[1]
        my_class = ClassDefinition(self, class_name)
        for attribute in parsed_class[2:]:
            match attribute:
                case [InterpreterBase.METHOD_DEF, m_return, m_name, m_params, m_body]:
                    my_class.add_method(m_name, m_return, m_params, m_body)
                case [InterpreterBase.FIELD_DEF, f_type, f_name, f_value]:
                    my_class.add_field(f_type, f_name, f_value)
        classes[class_name] = my_class

    def setup(self, parsed_program) -> None:
        self.setup_inheritance(parsed_program)
        for parsed_class in parsed_program:
            self.setup_class(parsed_class)

    def get_main_class(self) -> ClassDefinition:
        if InterpreterBase.MAIN_CLASS_DEF not in classes:
            self.error(ErrorType.NAME_ERROR)
        return classes[InterpreterBase.MAIN_CLASS_DEF]

    def run(self, program_source: list[str]) -> None:
        classes.clear()
        inheritance.clear()
        class_names.clear()
        classes[self.NULL_DEF] = ClassDefinition(self, self.NULL_DEF)
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
