# pylint: disable=too-few-public-methods

"""
# v2
- inheritance
  (class foo inherits bar ...)
  dynamic dispatch
  polymorphism
- static typing
.  update formal params to use VariableDef instead of just strings
.  check parameter type compatability on calls
.  change syntax for method definitions to:
   (method method_name ((type1 param1) (type2 param2) ...) (statement))
.  change MethodDef class to store typename and Type.??? instead of just strings for formal params
.  create new let statement, which is just like begin except it has locals
   (let ((type1 param1 val1) (type2 param2 val2)) (statement1) (statement2))
.  update environment to scope variables by block
.  update code to ensure variables go out of scope at end of block
.  change class syntax for field definitions:
   (field type name init_value)
.  update FieldDef class to support types of fields
.  need to support class names for types
.  update variable assignments to ensure types are consistent
.  update parameter passing code to make sure actual and formal args are consistent types
   . must handle polymorphism (passing subtype to f(supertype))
.  update overload checking code to check not only by # of parameters but by types in inheritance
.  have return type for methods
.  update return code to check return type of returned value
.  add void return type for methods that don't return a value
.  update method completion code to return default value (0, False, "", null) if no returned value
.  add test cases for returning a subclass (pass) of the return type, and a superclass (fail)
.  test for duplicate formal param names and generate error
.  test for invalid param types and return types
.  propagate type to null during return and when assigned to variable so we can't compare
   a null pointer of type person to a null pointer of type robot
"""

from typing import Literal, Optional, TYPE_CHECKING
from intbase import InterpreterBase, ErrorType
from type_valuev3 import Type, create_value, create_default_value, Value
from copy import deepcopy

if TYPE_CHECKING:
    from interpreterv3 import Interpreter


class VariableDef:
    # var_type is a Type() and value is a Value()
    def __init__(
        self, var_type: Type, var_name: str, value: Optional[Value] = None
    ) -> None:
        self.type: Type = var_type
        self.name: str = var_name
        self.value: Optional[Value] = value

    def set_value(self, value: Value) -> None:
        self.value = value


# parses and holds the definition of a member method
# [method return_type method_name [[type1 param1] [type2 param2] ...] [statement]]
class MethodDef:
    def __init__(self, method_source) -> None:
        self.line_num: int = method_source[0].line_num  # used for errors
        self.method_name: str = method_source[2]
        if method_source[1] == InterpreterBase.VOID_DEF:
            self.return_type: Type = Type(InterpreterBase.NOTHING_DEF)
        else:
            self.return_type = Type(method_source[1])
        self.formal_params: list[VariableDef] = self.__parse_params(method_source[3])
        self.code = method_source[4]

    def get_method_name(self) -> str:
        return self.method_name

    def get_formal_params(self) -> list[VariableDef]:
        return self.formal_params

    # returns a Type()
    def get_return_type(self) -> Type:
        return self.return_type

    def get_code(self):
        return self.code

    # input params in the form of [[type1 param1] [type2 param2] ...]
    # output is a set of VariableDefs
    def __parse_params(self, params: list) -> list[VariableDef]:
        formal_params: list[VariableDef] = []
        for param in params:
            var_def: VariableDef = VariableDef(Type(param[0]), param[1])
            formal_params.append(var_def)
        return formal_params


# holds definition for a class, including a list of all the fields and their default values, all
# of the methods in the class, and the superclass information (if any)
# v2 class definition: [class classname [inherits baseclassname] [field1] [field2] ... [method1] [method2] ...]
# [] denotes optional syntax
class ClassDef:
    def __init__(self, class_source, interpreter: "Interpreter") -> None:
        self.interpreter: Interpreter = interpreter
        self.name: str = class_source[1]
        self.class_source = class_source
        fields_and_methods_start_index: Literal[
            2, 4
        ] = self.__check_for_inheritance_and_set_superclass_info(class_source)
        self.__create_field_list(class_source[fields_and_methods_start_index:])
        self.__create_method_list(class_source[fields_and_methods_start_index:])

    # get the classname
    def get_name(self) -> str:
        return self.name

    # get a list of FieldDef objects for all fields in the class
    def get_fields(self) -> list[VariableDef]:
        return self.fields

    # get a list of MethodDef objects for all methods in the class
    def get_methods(self) -> list[MethodDef]:
        return self.methods

    # returns a ClassDef object
    def get_superclass(self) -> Optional["ClassDef"]:
        return self.super_class

    def __check_for_inheritance_and_set_superclass_info(
        self, class_source
    ) -> Literal[2, 4]:
        if class_source[2] != InterpreterBase.INHERITS_DEF:
            self.super_class: Optional[ClassDef] = None
            return 2  # fields and method definitions start after [class classname ...], jump to the correct place to continue parsing

        super_class_name: str = class_source[3]
        self.super_class = self.interpreter.get_class_def(
            super_class_name, class_source[0].line_num
        )
        return 4  # fields and method definitions start after [class classname inherits baseclassname ...]

    def __create_field_list(self, class_body) -> None:
        self.fields: list[
            VariableDef
        ] = []  # array of VariableDefs with default values set
        self.field_map: dict[str, VariableDef] = {}
        fields_defined_so_far: set[str] = set()
        for member in class_body:
            # member format is [field typename varname default_value]
            if member[0] == InterpreterBase.FIELD_DEF:
                if member[2] in fields_defined_so_far:  # redefinition
                    self.interpreter.error(
                        ErrorType.NAME_ERROR,
                        "duplicate field " + member[2],
                        member[0].line_num,
                    )
                var_def = self.__create_variable_def_from_field(member)
                self.fields.append(var_def)
                self.field_map[member[2]] = var_def
                fields_defined_so_far.add(member[2])

    # field def: [field typename varname defvalue]
    # returns a VariableDef object that represents that field
    def __create_variable_def_from_field(self, field_def) -> VariableDef:
        var_def: VariableDef
        field_type_parts: list[str] = field_def[1].split(
            InterpreterBase.TYPE_CONCAT_CHAR
        )
        if len(field_type_parts) > 1:
            if field_type_parts[0] not in self.interpreter.template_class_index:
                self.interpreter.error(
                    ErrorType.TYPE_ERROR,
                    f"No template class named {field_type_parts[0]} found",
                )
            if field_def[1] not in self.interpreter.class_index:
                # Add it to the class_index immediately to avoid infinite loops
                self.interpreter.class_index[field_def[1]] = None  # type:ignore
                self.interpreter.type_manager.add_class_type(field_def[1], None)
                template_class_def: TemplateClassDef = (
                    self.interpreter.template_class_index[field_type_parts[0]]
                )
                self.interpreter.class_index[
                    field_def[1]
                ] = template_class_def.instantiate_class(field_type_parts[1:])
        if len(field_def) < 4:
            var_def = VariableDef(
                Type(field_def[1]),
                field_def[2],
                create_default_value(Type(field_def[1])),
            )
        else:
            var_def = VariableDef(
                Type(field_def[1]), field_def[2], create_value(field_def[3])
            )
        if var_def.value is not None and not self.interpreter.check_type_compatibility(
            var_def.type, var_def.value.type(), True
        ):
            self.interpreter.error(
                ErrorType.TYPE_ERROR,
                "invalid type/type mismatch with field " + field_def[2],
                field_def[0].line_num,
            )
        return var_def

    def __create_method_list(self, class_body) -> None:
        self.methods: list[MethodDef] = []
        self.method_map: dict[str, MethodDef] = {}
        methods_defined_so_far: set[str] = set()
        for member in class_body:
            if member[0] == InterpreterBase.METHOD_DEF:
                method_def: MethodDef = MethodDef(member)
                if method_def.method_name in methods_defined_so_far:  # redefinition
                    self.interpreter.error(
                        ErrorType.NAME_ERROR,
                        "duplicate method " + method_def.method_name,
                        member[0].line_num,
                    )
                self.__check_method_names_and_types(method_def)
                self.methods.append(method_def)
                self.method_map[method_def.method_name] = method_def
                methods_defined_so_far.add(method_def.method_name)

    # for a given method, make sure that the parameter types are valid, return type is valid, and param names
    # are not duplicated
    def __check_method_names_and_types(self, method_def: MethodDef):
        return_type_parts: list[str] = method_def.return_type.type_name.split(
            InterpreterBase.TYPE_CONCAT_CHAR
        )
        if len(return_type_parts) > 1:
            if return_type_parts[0] not in self.interpreter.template_class_index:
                self.interpreter.error(
                    ErrorType.TYPE_ERROR,
                    f"Invalid template return type {method_def.return_type.type_name}",
                )
            if method_def.return_type.type_name not in self.interpreter.class_index:
                # Add it to the class_index immediately to avoid infinite loops
                self.interpreter.class_index[
                    method_def.return_type.type_name
                ] = None  # type:ignore
                self.interpreter.type_manager.add_class_type(
                    method_def.return_type.type_name, None
                )
                template_class_def: TemplateClassDef = (
                    self.interpreter.template_class_index[return_type_parts[0]]
                )
                self.interpreter.class_index[
                    method_def.return_type.type_name
                ] = template_class_def.instantiate_class(return_type_parts[1:])
        if not self.interpreter.is_valid_type(
            method_def.return_type.type_name
        ) and method_def.return_type != Type(
            InterpreterBase.NOTHING_DEF
        ):  # checks that return type isn't a defined type or void
            self.interpreter.error(
                ErrorType.TYPE_ERROR,
                "invalid return type for method " + method_def.method_name,
                method_def.line_num,
            )
        for param in method_def.formal_params:
            # LDJFLSKDFJSDLFKJSKLDFJKLSDFJLSDLKFDSKJLFLKJ
            var_def: VariableDef
            param_type: str = param.type.type_name
            param_type_parts: list[str] = param_type.split(
                InterpreterBase.TYPE_CONCAT_CHAR
            )
            if len(param_type_parts) > 1:
                if param_type_parts[0] not in self.interpreter.template_class_index:
                    self.interpreter.error(
                        ErrorType.TYPE_ERROR,
                        f"No template class named {param_type_parts[0]} found",
                    )
                if param_type not in self.interpreter.class_index:
                    # Add it to the class_index immediately to avoid infinite loops
                    self.interpreter.class_index[param_type] = None  # type:ignore
                    self.interpreter.type_manager.add_class_type(param_type, None)
                    template_class_def: TemplateClassDef = (
                        self.interpreter.template_class_index[param_type_parts[0]]
                    )
                    self.interpreter.class_index[
                        param_type
                    ] = template_class_def.instantiate_class(param_type_parts[1:])
            # LDJFLSKDFJSDLFKJSKLDFJKLSDFJLSDLKFDSKJLFLKJ
            if not self.interpreter.is_valid_type(param.type.type_name):
                self.interpreter.error(
                    ErrorType.TYPE_ERROR,
                    "invalid type for parameter " + param.name,
                    method_def.line_num,
                )


class TemplateClassDef:
    def __init__(self, class_source, interpreter: "Interpreter") -> None:
        self.interpreter: Interpreter = interpreter
        self.name: str = class_source[1]
        self.class_source = class_source
        self.templated_types: list[str] = class_source[2]
        self.__validate(class_source)

    def __replace(self, code, template_to_actual: dict[str, str]):
        if isinstance(code, str):
            if code in template_to_actual:
                return template_to_actual[code]
            code_parts: list[str] = code.split(InterpreterBase.TYPE_CONCAT_CHAR)
            if len(code_parts) > 1:
                return InterpreterBase.TYPE_CONCAT_CHAR.join(
                    [
                        template_to_actual[c] if c in template_to_actual else c
                        for c in code_parts
                    ]
                )
            return code
        else:
            return [self.__replace(c, template_to_actual) for c in code]

    def __validate(self, code) -> None:
        if isinstance(code, str):
            code_parts: list[str] = code.split(InterpreterBase.TYPE_CONCAT_CHAR)
            if len(code_parts) > 1:
                for part in code_parts[1:]:
                    if (
                        not self.interpreter.is_valid_type(part)
                        and part not in self.templated_types
                    ):
                        self.interpreter.error(
                            ErrorType.TYPE_ERROR,
                            f"Invalid type {part} provided for templated class {self.name}",
                        )
        else:
            for part in code:
                self.__validate(part)

    def instantiate_class(self, actual_types: list[str]) -> ClassDef:
        if len(self.templated_types) != len(actual_types):
            self.interpreter.error(
                ErrorType.TYPE_ERROR,
                f"Wrong number of types provided for object of type {self.name}",
            )
        template_to_actual: dict[str, str] = {}
        for template, actual in zip(self.templated_types, actual_types):
            template_to_actual[template] = actual
        source = deepcopy(self.class_source)
        source[0] = self.interpreter.CLASS_DEF
        source[
            1
        ] += self.interpreter.TYPE_CONCAT_CHAR + self.interpreter.TYPE_CONCAT_CHAR.join(
            actual_types
        )
        source.pop(2)
        return ClassDef(self.__replace(source, template_to_actual), self.interpreter)
