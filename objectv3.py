from typing import Any, cast, TYPE_CHECKING, Optional
import copy
from env_v3 import EnvironmentManager
from intbase import InterpreterBase, ErrorType
from type_valuev3 import create_value, create_default_value, Type, Value
from bparser import StringWithLineNumber
from classv3 import VariableDef

if TYPE_CHECKING:
    from classv3 import MethodDef, ClassDef, TemplateClassDef
    from interpreterv3 import Interpreter


class ObjectDef:
    # statement execution results
    STATUS_PROCEED: int = 0
    STATUS_RETURN: int = 1
    STATUS_EXCEPTION: int = 2

    # type constants
    INT_TYPE_CONST: Type = Type(InterpreterBase.INT_DEF)
    STRING_TYPE_CONST: Type = Type(InterpreterBase.STRING_DEF)
    BOOL_TYPE_CONST: Type = Type(InterpreterBase.BOOL_DEF)

    # class_def is a ClassDef object
    def __init__(
        self,
        interpreter: "Interpreter",
        class_def: "ClassDef",
        anchor_object: Optional["ObjectDef"] = None,
        trace_output: bool = False,
    ):
        self.interpreter: "Interpreter" = interpreter  # objref to interpreter object. used to report errors, get input, produce output
        self.class_def: "ClassDef" = class_def

        if anchor_object is None:
            self.anchor_object: ObjectDef = self
        else:
            self.anchor_object = anchor_object
        self.trace_output = trace_output
        self.__instantiate_fields()
        self.__map_method_names_to_method_definitions()
        self.__create_map_of_operations_to_lambdas()  # sets up maps to facilitate binary and unary operations, e.g., (+ 5 6)
        self.__init_superclass_if_any()  # construct default values for superclass fields all the way to the base class

    def __get_obj_with_method(
        self, start_obj: "ObjectDef", method_name: str, actual_params
    ) -> Optional["ObjectDef"]:
        cur_obj: Optional[ObjectDef] = start_obj
        while cur_obj is not None:
            if method_name not in cur_obj.methods:
                cur_obj = cur_obj.super_object
                continue
            method_def = cur_obj.methods[method_name]
            if len(actual_params) == len(
                method_def.formal_params
            ) and self.__compatible_param_types(
                actual_params, method_def.formal_params
            ):
                break
            cur_obj = cur_obj.super_object
        return cur_obj

    # actual_params is a list of Value objects; all parameters are passed by value
    # the caller passes in its line number so if there's an error (e.g., mismatched # of parameters or unknown
    # method name) we can generate an error at the source (where the call is initiated) for better context
    def call_method(
        self,
        method_name: str,
        actual_params: list[Optional[Value]],
        super_only: bool,
        line_num_of_caller,
    ) -> tuple[int, Optional[Value]]:
        # check to see if we have a method in this class or its base class(es) matching this signature
        if self.__get_obj_with_method(self, method_name, actual_params) is None:
            self.interpreter.error(
                ErrorType.NAME_ERROR,
                "unknown method " + method_name,
                line_num_of_caller,
            )

        # Yes, we have a method with the right name/parameters known to this class or its base classes...
        # So now find the proper version of the method in the most-derived class, which may be in a derived class
        # of this class!  Start from the anchor object (most derived part of the object) and search for the most
        # derived object part that has this method.
        if super_only:
            anchor = self
        else:
            anchor = self.anchor_object
        obj_to_call_on = self.__get_obj_with_method(anchor, method_name, actual_params)
        if obj_to_call_on is None:
            return ObjectDef.STATUS_PROCEED, None

        method_def = obj_to_call_on.methods[method_name]

        # handle the call in the object
        env: EnvironmentManager = (
            EnvironmentManager()
        )  # maintains lexical environment for function; just params for now
        for formal, actual in zip(method_def.formal_params, actual_params):
            if actual is None:
                return ObjectDef.STATUS_PROCEED, None
            formal_copy = copy.copy(formal)  # VariableDef obj.
            formal_copy.set_value(actual)  # actual is a Value obj.
            if not env.create_new_symbol(formal_copy.name):
                self.interpreter.error(
                    ErrorType.NAME_ERROR,
                    "duplicate formal param name " + formal.name,
                    method_def.line_num,
                )
            env.set(formal_copy.name, formal_copy)
        # since each method has a single top-level statement, execute it.
        status, return_value = obj_to_call_on.__execute_statement(
            env, method_def.return_type, method_def.code
        )
        # if the method explicitly used the (return expression) statement to return a value, then return that
        # value back to the caller
        if status == ObjectDef.STATUS_RETURN and return_value is not None:
            return ObjectDef.STATUS_PROCEED, return_value
        elif status == ObjectDef.STATUS_EXCEPTION:
            return ObjectDef.STATUS_EXCEPTION, return_value
        # The method didn't explicitly return a value, so return the default return type for the method
        return ObjectDef.STATUS_PROCEED, create_default_value(
            method_def.get_return_type()
        )

    # def get_me_as_value(self):
    #     return Value(Type(self.class_def.name), self)

    def get_me_as_value(self) -> Value:
        anchor = self.anchor_object
        return Value(Type(anchor.class_def.name), anchor)

    # checks whether each formal parameter has a compatible type with the actual parameter
    def __compatible_param_types(
        self, actual_params: list[Value], formal_params: list[VariableDef]
    ) -> bool:
        for formal, actual in zip(formal_params, actual_params):
            if not self.interpreter.check_type_compatibility(
                formal.type, actual.type(), True
            ):
                return False
        return True

    # returns (status_code, return_value) where:
    # - status_code indicates whether the statement (or one of its sub-statements) executed a return command and thus
    #   the current method needs to terminate immediately, or whether the statement simply ran but didn't execute a
    #   return statement, and thus the next statement in the method should run normally
    # - return value is a value of type Value which is the returned value from the function
    def __execute_statement(
        self, env: EnvironmentManager, return_type: Type, code
    ) -> tuple[int, Optional[Value]]:
        if self.trace_output:
            print(f"{code[0].line_num}: {code}")
        tok: StringWithLineNumber = code[0]
        if tok == InterpreterBase.BEGIN_DEF:
            return self.__execute_begin(env, return_type, code)
        elif tok == InterpreterBase.SET_DEF:
            return self.__execute_set(env, code)
        elif tok == InterpreterBase.IF_DEF:
            return self.__execute_if(env, return_type, code)
        elif tok == InterpreterBase.CALL_DEF:
            return self.__execute_call(env, code)[1]
        elif tok == InterpreterBase.WHILE_DEF:
            return self.__execute_while(env, return_type, code)
        elif tok == InterpreterBase.RETURN_DEF:
            return self.__execute_return(env, return_type, code)
        elif tok == InterpreterBase.THROW_DEF:
            return self.__execute_throw(env, code)
        elif tok == InterpreterBase.TRY_DEF:
            return self.__execute_try(env, return_type, code)
        elif tok == InterpreterBase.INPUT_STRING_DEF:
            return self.__execute_input(env, code, True)
        elif tok == InterpreterBase.INPUT_INT_DEF:
            return self.__execute_input(env, code, False)
        elif tok == InterpreterBase.PRINT_DEF:
            return self.__execute_print(env, code)
        elif tok == InterpreterBase.LET_DEF:
            return self.__execute_let(env, return_type, code)
        else:
            # Report error via interpreter
            self.interpreter.error(
                ErrorType.SYNTAX_ERROR, "unknown statement " + tok, tok.line_num
            )

    # This method is used for both the begin and let statements
    # (begin (statement1) (statement2) ... (statementn))
    # (let ((type1 var1 defaultvalue1) ... (typen varn defaultvaluen)) (statement1) ... (statementn))
    def __execute_begin(
        self, env: EnvironmentManager, return_type: Type, code, has_vardef: bool = False
    ):
        if has_vardef:  # handles the let case
            code_start = 2
            env.block_nest()
            self.__add_locals_to_env(env, code[1], code[0].line_num)
        else:  # handles the begin case
            code_start = 1

        status = ObjectDef.STATUS_PROCEED
        return_value = None
        for statement in code[code_start:]:
            status, return_value = self.__execute_statement(env, return_type, statement)
            if (
                status == ObjectDef.STATUS_RETURN
                or status == ObjectDef.STATUS_EXCEPTION
            ):
                break
        # if we run through the entire block without a return, then just return proceed
        # we don't want the enclosing block to exit with a return
        if has_vardef:
            env.block_unnest()
        return status, return_value  # could be a valid return of a value or an error

    # add all local variables defined in a let to the environment
    def __add_locals_to_env(self, env, var_defs, line_number) -> None:
        for var_def in var_defs:
            if var_def[0] not in self.interpreter.class_index:
                var_type_parts: list[str] = var_def[0].split(
                    InterpreterBase.TYPE_CONCAT_CHAR
                )
                if len(var_type_parts) > 1:
                    template_class_def: TemplateClassDef = (
                        self.interpreter.template_class_index[var_type_parts[0]]
                    )
                    self.interpreter.class_index[
                        var_def[0]
                    ] = template_class_def.instantiate_class(var_type_parts[1:])
                    self.interpreter.type_manager.add_class_type(var_def[0], None)
            # vardef in the form of (typename varname defvalue)
            var_type: Type = Type(var_def[0])
            var_name: str = var_def[1]
            default_value: Optional[Value]
            if len(var_def) < 3:
                default_value = create_default_value(var_type)
            else:
                default_value = create_value(var_def[2])
            if default_value is None:
                return
            # make sure default value for each local is of a matching type
            self.__check_type_compatibility(
                var_type, default_value.type(), True, line_number
            )
            if not env.create_new_symbol(var_name):
                self.interpreter.error(
                    ErrorType.NAME_ERROR,
                    "duplicate local variable name " + var_name,
                    line_number,
                )
            var_def = VariableDef(var_type, var_name, default_value)
            env.set(var_name, var_def)

    # (let ((type1 var1 defval1) (type2 var2 defval2)) (statement1) (statement2) ...)
    # uses helper function __execute_begin to implement its functionality
    def __execute_let(self, env, return_type, code):
        return self.__execute_begin(env, return_type, code, True)

    # (call object_ref/me methodname param1 param2 param3)
    # where params are expressions, and expresion could be a value, or a (+ ...)
    # statement version of a method call; there's also an expression version of a method call below
    def __execute_call(self, env, code):
        return ObjectDef.STATUS_PROCEED, self.__execute_call_aux(
            env, code, code[0].line_num
        )

    # (set varname expression), where expression could be a value, or a (+ ...)
    def __execute_set(
        self, env: EnvironmentManager, code
    ) -> tuple[int, Optional[Value]]:
        status, val = self.__evaluate_expression(env, code[2], code[0].line_num)
        if status == ObjectDef.STATUS_EXCEPTION:
            return status, val
        self.__set_variable_aux(
            env, code[1], val, code[0].line_num
        )  # checks/reports type and name errors
        return ObjectDef.STATUS_PROCEED, None

    # (return expression) where expresion could be a value, or a (+ ...)
    def __execute_return(
        self, env: EnvironmentManager, return_type: Type, code
    ) -> tuple[int, Optional[Value]]:
        if len(code) == 1:
            # [return] with no return value; return default value for type
            return ObjectDef.STATUS_RETURN, None
        else:
            status, result = self.__evaluate_expression(env, code[1], code[0].line_num)
            if status == ObjectDef.STATUS_EXCEPTION:
                return status, result
            # CAREY FIX
            if result is not None and result.is_typeless_null():
                self.__check_type_compatibility(
                    return_type, result.type(), True, code[0].line_num
                )
                result = Value(return_type, None)  # propagate return type to null ###
        self.__check_type_compatibility(
            return_type, result.type(), True, code[0].line_num  # type:ignore
        )
        return ObjectDef.STATUS_RETURN, result

    # (try try_block catch_block) where expresion evaluates to a string
    def __execute_try(
        self, env: EnvironmentManager, return_type: Type, code
    ) -> tuple[int, Optional[Value]]:
        result: tuple[int, Optional[Value]] = self.__execute_statement(
            env, return_type, code[1]
        )
        if result[0] == ObjectDef.STATUS_EXCEPTION:
            env.block_nest()
            env.create_new_symbol(InterpreterBase.EXCEPTION_VARIABLE_DEF)
            env.set(
                InterpreterBase.EXCEPTION_VARIABLE_DEF,
                VariableDef(
                    Type(InterpreterBase.STRING_DEF),
                    InterpreterBase.EXCEPTION_VARIABLE_DEF,
                    result[1],
                ),
            )
            result = self.__execute_statement(env, return_type, code[2])
            env.block_unnest()
        return result

    # (throw expression) where expresion evaluates to a string
    def __execute_throw(
        self, env: EnvironmentManager, code
    ) -> tuple[int, Optional[Value]]:
        status, result = self.__evaluate_expression(
            env, code[1], code[0].line_num
        )  # FIXME: Check status
        if status == ObjectDef.STATUS_EXCEPTION:
            return status, result
        if result is None or result.type().type_name != InterpreterBase.STRING_DEF:
            self.interpreter.error(
                ErrorType.TYPE_ERROR,
                "Tried to throw non-string error",
                code[0].line_num,
            )
        return ObjectDef.STATUS_EXCEPTION, result

    # (print expression1 expression2 ...) where expresion could be a variable, value, or a (+ ...)
    def __execute_print(self, env, code) -> tuple[int, Optional[Value]]:
        output = ""
        for expr in code[1:]:
            # TESTING NOTE: Will not test printing of object references
            status, term = self.__evaluate_expression(env, expr, code[0].line_num)
            if status == ObjectDef.STATUS_EXCEPTION:
                return status, term
            if term is None:
                self.interpreter.error(
                    ErrorType.TYPE_ERROR, "Tried to print None", code[0].line_num
                )
            val = term.value()
            typ = term.type()
            if typ == ObjectDef.BOOL_TYPE_CONST:
                if val == True:
                    val = "true"
                else:
                    val = "false"
            # document will never print out an obj ref
            output += str(val)
        self.interpreter.output(output)
        return ObjectDef.STATUS_PROCEED, None

    # (inputs target_variable) or (inputi target_variable) sets target_variable to input string/int
    def __execute_input(
        self, env: EnvironmentManager, code, get_string: bool
    ) -> tuple[int, None]:
        inp = cast(str, self.interpreter.get_input())
        if get_string:
            val = Value(ObjectDef.STRING_TYPE_CONST, inp)
        else:
            val = Value(ObjectDef.INT_TYPE_CONST, int(inp))

        self.__set_variable_aux(env, code[1], val, code[0].line_num)
        return ObjectDef.STATUS_PROCEED, None

    # helper method used to set either parameter variables or member fields; parameters currently shadow
    # member fields
    def __set_variable_aux(
        self, env: EnvironmentManager, var_name: str, value: Optional[Value], line_num
    ) -> None:
        if value is None:
            return
        # parameters shadows fields, locals shadow parameters (and outer-block locals)
        if self.__set_local_or_param(
            env, var_name, value, line_num
        ):  # may report a type error
            return
        if self.__set_field(var_name, value, line_num):  # may report a type error
            return
        self.interpreter.error(
            ErrorType.NAME_ERROR, "unknown field/variable " + var_name, line_num
        )

    # (if expression (statement) (statement) ) where expresion could be a boolean constant (e.g., true), member
    # variable without ()s, or a boolean expression in parens, like (> 5 a)
    def __execute_if(self, env, return_type, code) -> tuple[int, Optional[Value]]:
        status, condition = self.__evaluate_expression(env, code[1], code[0].line_num)
        if status == ObjectDef.STATUS_EXCEPTION:
            return status, condition
        if condition is None or condition.type() != ObjectDef.BOOL_TYPE_CONST:
            self.interpreter.error(
                ErrorType.TYPE_ERROR,
                "non-boolean if condition " + " ".join(x for x in code[1]),
                code[0].line_num,
            )
        if condition.value():
            status, return_value = self.__execute_statement(
                env, return_type, code[2]
            )  # if condition was true
            return status, return_value
        elif len(code) == 4:
            status, return_value = self.__execute_statement(
                env, return_type, code[3]
            )  # if condition was false, do else
            return status, return_value
        else:
            return ObjectDef.STATUS_PROCEED, None

    # (while expression (statement) ) where expresion could be a boolean value, boolean member variable,
    # or a boolean expression in parens, like (> 5 a)
    def __execute_while(self, env, return_type, code):
        while True:
            status, condition = self.__evaluate_expression(
                env, code[1], code[0].line_num
            )
            if status == ObjectDef.STATUS_EXCEPTION:
                return status, condition
            if condition is None or condition.type() != ObjectDef.BOOL_TYPE_CONST:
                self.interpreter.error(
                    ErrorType.TYPE_ERROR,
                    "non-boolean while condition " + " ".join(x for x in code[1]),
                    code[0].line_num,
                )
            if not condition.value():  # condition is false, exit loop immediately
                return ObjectDef.STATUS_PROCEED, None
            # condition is true, run body of while loop
            status, return_value = self.__execute_statement(env, return_type, code[2])
            if (
                status == ObjectDef.STATUS_EXCEPTION
                or status == ObjectDef.STATUS_RETURN
            ):
                return (
                    status,
                    return_value,
                )  # could be a valid return of a value or an error

    # var_def is a VariableDef
    # this method checks to see if a variable holds a null value, and if so, changes the type of the null value
    # to the type of the variable, e.g.,
    def __propagate_type_to_null(self, var_def: VariableDef) -> Value:
        if var_def.value is None or var_def.value.is_null():
            return Value(var_def.type, None)
        return var_def.value

    # given an expression, return a Value object with the expression's evaluated result
    # expressions could be: constants (true, 5, "blah"), variables (e.g., x), arithmetic/string/logical expressions
    # like (+ 5 6), (+ "abc" "def"), (> a 5), method calls (e.g., (call me foo)), or instantiations (e.g., new dog_class)
    def __evaluate_expression(
        self, env: EnvironmentManager, expr, line_num_of_statement: int
    ) -> tuple[int, Optional[Value]]:
        if type(expr) is not list:
            # locals shadow member variables
            var_def = env.get(expr)
            if var_def is not None:
                return ObjectDef.STATUS_PROCEED, self.__propagate_type_to_null(var_def)
            elif expr in self.fields:
                return ObjectDef.STATUS_PROCEED, self.__propagate_type_to_null(
                    self.fields[expr]
                )  # return the Value object
            # need to check for variable name and get its value too
            value = create_value(expr)
            if value is not None:
                return ObjectDef.STATUS_PROCEED, value
            if expr == InterpreterBase.ME_DEF:
                return ObjectDef.STATUS_PROCEED, (
                    self.get_me_as_value()
                )  # create Value object for current object with right type
            self.interpreter.error(
                ErrorType.NAME_ERROR,
                "invalid field or parameter " + expr,
                line_num_of_statement,
            )

        operator = expr[0]
        if operator in self.binary_op_list:
            status1, operand1 = self.__evaluate_expression(
                env, expr[1], line_num_of_statement
            )
            if status1 == ObjectDef.STATUS_EXCEPTION:
                return status1, operand1
            status2, operand2 = self.__evaluate_expression(
                env, expr[2], line_num_of_statement
            )
            if status2 == ObjectDef.STATUS_EXCEPTION:
                return status2, operand2

            if operand1 is None or operand2 is None:
                self.interpreter.error(ErrorType.TYPE_ERROR)
            if (
                operand1.type() == operand2.type()
                and operand1.type() == ObjectDef.INT_TYPE_CONST
            ):
                if operator not in self.binary_ops[InterpreterBase.INT_DEF]:
                    self.interpreter.error(
                        ErrorType.TYPE_ERROR,
                        "invalid operator applied to ints",
                        line_num_of_statement,
                    )
                return ObjectDef.STATUS_PROCEED, self.binary_ops[
                    InterpreterBase.INT_DEF
                ][operator](operand1, operand2)
            if (
                operand1.type() == operand2.type()
                and operand1.type() == ObjectDef.STRING_TYPE_CONST
            ):
                if operator not in self.binary_ops[InterpreterBase.STRING_DEF]:
                    self.interpreter.error(
                        ErrorType.TYPE_ERROR,
                        "invalid operator applied to strings",
                        line_num_of_statement,
                    )
                return ObjectDef.STATUS_PROCEED, self.binary_ops[
                    InterpreterBase.STRING_DEF
                ][operator](operand1, operand2)
            if (
                operand1.type() == operand2.type()
                and operand1.type() == ObjectDef.BOOL_TYPE_CONST
            ):
                if operator not in self.binary_ops[InterpreterBase.BOOL_DEF]:
                    self.interpreter.error(
                        ErrorType.TYPE_ERROR,
                        "invalid operator applied to bool",
                        line_num_of_statement,
                    )
                return ObjectDef.STATUS_PROCEED, self.binary_ops[
                    InterpreterBase.BOOL_DEF
                ][operator](operand1, operand2)
            # handle object reference comparisons last
            if self.interpreter.check_type_compatibility(
                operand1.type(), operand2.type(), False
            ):
                return ObjectDef.STATUS_PROCEED, self.binary_ops[
                    InterpreterBase.CLASS_DEF
                ][operator](operand1, operand2)
            self.interpreter.error(
                ErrorType.TYPE_ERROR,
                f"operator {operator} applied to two incompatible types",
                line_num_of_statement,
            )
        if operator in self.unary_op_list:
            status, operand = self.__evaluate_expression(
                env, expr[1], line_num_of_statement
            )
            if status == ObjectDef.STATUS_EXCEPTION:
                return status, operand
            if operand is None:
                self.interpreter.error(ErrorType.TYPE_ERROR)
            if operand.type() == ObjectDef.BOOL_TYPE_CONST:
                if operator not in self.unary_ops[InterpreterBase.BOOL_DEF]:
                    self.interpreter.error(
                        ErrorType.TYPE_ERROR,
                        "invalid unary operator applied to bool",
                        line_num_of_statement,
                    )
                return ObjectDef.STATUS_PROCEED, self.unary_ops[
                    InterpreterBase.BOOL_DEF
                ][operator](operand)

        # handle call expression: (call objref methodname p1 p2 p3)
        if operator == InterpreterBase.CALL_DEF:
            return self.__execute_call_aux(env, expr, line_num_of_statement)
        # handle new expression: (new classname)
        if operator == InterpreterBase.NEW_DEF:
            return ObjectDef.STATUS_PROCEED, self.__execute_new_aux(
                env, expr, line_num_of_statement
            )
        return ObjectDef.STATUS_PROCEED, None

    # (new classname)
    def __execute_new_aux(
        self, env: EnvironmentManager, code, line_num_of_statement: int
    ):
        class_name = code[1]
        obj = self.interpreter.instantiate(code[1], line_num_of_statement)
        return Value(Type(class_name), obj)

    # this method is a helper used by call statements and call expressions
    # (call object_ref/me methodname p1 p2 p3)
    def __execute_call_aux(
        self, env: EnvironmentManager, code, line_num_of_statement: int
    ) -> tuple[int, Optional[Value]]:
        # determine which object we want to call the method on
        super_only: bool = False
        obj_name: str = code[1]
        if obj_name == InterpreterBase.ME_DEF:
            obj: ObjectDef = self
        elif obj_name == InterpreterBase.SUPER_DEF:
            if not self.super_object:
                self.interpreter.error(
                    ErrorType.TYPE_ERROR,
                    "invalid call to super object by class "
                    + self.class_def.get_name(),
                    line_num_of_statement,
                )
            obj = self.super_object
            super_only = True
        else:
            # return a Value() object which has a type and a value
            status, obj_val = self.__evaluate_expression(
                env, obj_name, line_num_of_statement
            )
            if status == ObjectDef.STATUS_EXCEPTION:
                return status, obj_val
            if obj_val is None:
                return ObjectDef.STATUS_PROCEED, None
            if obj_val.is_null():
                self.interpreter.error(
                    ErrorType.FAULT_ERROR, "null dereference", line_num_of_statement
                )
            obj = cast(ObjectDef, obj_val.value())
        # prepare the actual arguments for passing
        actual_args: list[Optional[Value]] = []
        for expr in code[3:]:
            status, arg = self.__evaluate_expression(env, expr, line_num_of_statement)
            if status == ObjectDef.STATUS_EXCEPTION:
                return status, arg
            actual_args.append(arg)
        return obj.call_method(code[2], actual_args, super_only, line_num_of_statement)

    def __map_method_names_to_method_definitions(self) -> None:
        self.methods: dict[str, MethodDef] = {}
        for method in self.class_def.get_methods():
            self.methods[method.method_name] = method

    def __instantiate_fields(self) -> None:
        self.fields: dict[str, VariableDef] = {}
        # get_fields() returns a set of VariableDefs
        for vardef in self.class_def.get_fields():
            self.fields[vardef.name] = copy.copy(vardef)

    def __set_field(self, field_name: str, value: Value, line_num: int) -> bool:
        if field_name not in self.fields:
            return False
        var_def: VariableDef = self.fields[field_name]
        self.__check_type_compatibility(var_def.type, value.type(), True, line_num)
        var_def.set_value(value)
        return True

    def __set_local_or_param(
        self, env: EnvironmentManager, var_name: str, value: Value, line_num: int
    ) -> bool:
        var_def: Optional[VariableDef] = env.get(var_name)
        if var_def is None:
            return False
        self.__check_type_compatibility(var_def.type, value.type(), True, line_num)
        var_def.set_value(value)
        return True

    def __check_type_compatibility(
        self, lvalue_type: Type, rvalue_type: Type, for_assignment: bool, line_num: int
    ) -> None:
        if not self.interpreter.check_type_compatibility(
            lvalue_type, rvalue_type, for_assignment
        ):
            self.interpreter.error(
                ErrorType.TYPE_ERROR,
                f"type mismatch {lvalue_type.type_name} and {rvalue_type.type_name}",
                line_num,
            )

    def __create_map_of_operations_to_lambdas(self) -> None:
        self.binary_op_list: list[str] = [
            "+",
            "-",
            "*",
            "/",
            "%",
            "==",
            "!=",
            "<",
            "<=",
            ">",
            ">=",
            "&",
            "|",
        ]
        self.unary_op_list: list[str] = ["!"]
        self.binary_ops: dict[str, dict[str, Any]] = {}
        self.binary_ops[InterpreterBase.INT_DEF] = {
            "+": lambda a, b: Value(ObjectDef.INT_TYPE_CONST, a.value() + b.value()),
            "-": lambda a, b: Value(ObjectDef.INT_TYPE_CONST, a.value() - b.value()),
            "*": lambda a, b: Value(ObjectDef.INT_TYPE_CONST, a.value() * b.value()),
            "/": lambda a, b: Value(
                ObjectDef.INT_TYPE_CONST, a.value() // b.value()
            ),  # // for integer ops
            "%": lambda a, b: Value(ObjectDef.INT_TYPE_CONST, a.value() % b.value()),
            "==": lambda a, b: Value(ObjectDef.BOOL_TYPE_CONST, a.value() == b.value()),
            "!=": lambda a, b: Value(ObjectDef.BOOL_TYPE_CONST, a.value() != b.value()),
            ">": lambda a, b: Value(ObjectDef.BOOL_TYPE_CONST, a.value() > b.value()),
            "<": lambda a, b: Value(ObjectDef.BOOL_TYPE_CONST, a.value() < b.value()),
            ">=": lambda a, b: Value(ObjectDef.BOOL_TYPE_CONST, a.value() >= b.value()),
            "<=": lambda a, b: Value(ObjectDef.BOOL_TYPE_CONST, a.value() <= b.value()),
        }
        self.binary_ops[InterpreterBase.STRING_DEF] = {
            "+": lambda a, b: Value(ObjectDef.STRING_TYPE_CONST, a.value() + b.value()),
            "==": lambda a, b: Value(ObjectDef.BOOL_TYPE_CONST, a.value() == b.value()),
            "!=": lambda a, b: Value(ObjectDef.BOOL_TYPE_CONST, a.value() != b.value()),
            ">": lambda a, b: Value(ObjectDef.BOOL_TYPE_CONST, a.value() > b.value()),
            "<": lambda a, b: Value(ObjectDef.BOOL_TYPE_CONST, a.value() < b.value()),
            ">=": lambda a, b: Value(ObjectDef.BOOL_TYPE_CONST, a.value() >= b.value()),
            "<=": lambda a, b: Value(ObjectDef.BOOL_TYPE_CONST, a.value() <= b.value()),
        }
        self.binary_ops[InterpreterBase.BOOL_DEF] = {
            "&": lambda a, b: Value(ObjectDef.BOOL_TYPE_CONST, a.value() and b.value()),
            "|": lambda a, b: Value(ObjectDef.BOOL_TYPE_CONST, a.value() or b.value()),
            "==": lambda a, b: Value(ObjectDef.BOOL_TYPE_CONST, a.value() == b.value()),
            "!=": lambda a, b: Value(ObjectDef.BOOL_TYPE_CONST, a.value() != b.value()),
        }
        self.binary_ops[InterpreterBase.CLASS_DEF] = {
            "==": lambda a, b: Value(ObjectDef.BOOL_TYPE_CONST, a.value() == b.value()),
            "!=": lambda a, b: Value(ObjectDef.BOOL_TYPE_CONST, a.value() != b.value()),
        }

        self.unary_ops: dict[str, dict[str, Any]] = {}
        self.unary_ops[InterpreterBase.BOOL_DEF] = {
            "!": lambda a: Value(ObjectDef.BOOL_TYPE_CONST, not a.value()),
        }

    def __init_superclass_if_any(self) -> None:
        superclass_def = self.class_def.get_superclass()
        if superclass_def is None:
            self.super_object = None
            return

        self.super_object = ObjectDef(
            self.interpreter, superclass_def, self.anchor_object, self.trace_output
        )
