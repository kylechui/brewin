from typing import Optional
from classv3 import ClassDef, TemplateClassDef
from intbase import InterpreterBase, ErrorType
from bparser import BParser
from objectv3 import ObjectDef
from type_valuev3 import TypeManager, Type


# Main interpreter class
class Interpreter(InterpreterBase):
    def __init__(self, console_output=True, inp=None, trace_output=False) -> None:
        super().__init__(console_output, inp)
        self.trace_output = trace_output

    # run a program, provided in an array of strings, one string per line of source code
    # usese the provided BParser class found in parser.py to parse the program into lists
    def run(self, program) -> None:
        status, parsed_program = BParser.parse(program)
        if not status:
            super().error(
                ErrorType.SYNTAX_ERROR, f"Parse error on program: {parsed_program}"
            )
        self.__add_all_class_types_to_type_manager(parsed_program)
        self.__map_class_names_to_class_defs(parsed_program)

        # instantiate main class
        invalid_line_num_of_caller = None
        self.main_object = self.instantiate(
            InterpreterBase.MAIN_CLASS_DEF, invalid_line_num_of_caller
        )

        # call main function in main class; return value is ignored from main
        self.main_object.call_method(
            InterpreterBase.MAIN_FUNC_DEF, [], False, invalid_line_num_of_caller
        )

        # program terminates!

    # user passes in the line number of the statement that performed the new command so we can generate an error
    # if the user tries to new an class name that does not exist. This will report the line number of the statement
    # with the new command
    def instantiate(
        self, class_name: str, line_num_of_statement: Optional[int]
    ) -> ObjectDef:
        if class_name not in self.class_index:
            class_parts: list[str] = class_name.split(InterpreterBase.TYPE_CONCAT_CHAR)
            if class_parts[0] not in self.template_class_index:
                super().error(
                    ErrorType.TYPE_ERROR,
                    f"No class named {class_parts[0]} found",
                    line_num_of_statement,
                )
            for template_type in class_parts[1:]:
                if not self.is_valid_type(template_type) and template_type not in self.type_manager.primitive_types:
                    super().error(
                        ErrorType.TYPE_ERROR,
                        f"Invalid template type for new object of type {class_name}",
                        line_num_of_statement,
                    )
            self.type_manager.add_class_type(class_name, None)
            template_class_def: TemplateClassDef = self.template_class_index[class_parts[0]]
            self.class_index[class_name] = template_class_def.instantiate_class(class_parts[1:])
        class_def: ClassDef = self.class_index[class_name]
        obj = ObjectDef(
            self, class_def, None, self.trace_output
        )  # Create an object based on this class definition
        return obj

    # returns a ClassDef object
    def get_class_def(self, class_name: str, line_number_of_statement: int) -> ClassDef:
        if class_name not in self.class_index:
            super().error(
                ErrorType.TYPE_ERROR,
                f"No class named {class_name} found",
                line_number_of_statement,
            )
        return self.class_index[class_name]

    # returns a bool
    def is_valid_type(self, typename: str) -> bool:
        return self.type_manager.is_valid_type(typename)

    # returns a bool
    def is_a_subtype(self, suspected_supertype: str, suspected_subtype: str) -> bool:
        return self.type_manager.is_a_subtype(suspected_supertype, suspected_subtype)

    # typea and typeb are Type objects; returns true if the two type are compatible
    # for assignments typea is the type of the left-hand-side variable, and typeb is the type of the
    # right-hand-side variable, e.g., (set person_obj_ref (new teacher))
    def check_type_compatibility(
        self, typea: Type, typeb: Type, for_assignment: bool = False
    ) -> bool:
        return self.type_manager.check_type_compatibility(typea, typeb, for_assignment)

    def __map_class_names_to_class_defs(self, program) -> None:
        self.class_index: dict[str, ClassDef] = {}
        self.template_class_index: dict[str, TemplateClassDef] = {}
        for item in program:
            if item[0] == InterpreterBase.CLASS_DEF:
                if item[1] in self.class_index or item[1] in self.template_class_index:
                    super().error(
                        ErrorType.TYPE_ERROR,
                        f"Duplicate class name {item[1]}",
                        item[0].line_num,
                    )
                self.class_index[item[1]] = ClassDef(item, self)
            elif item[0] == InterpreterBase.TEMPLATE_CLASS_DEF:
                if item[1] in self.class_index or item[1] in self.template_class_index:
                    super().error(
                        ErrorType.TYPE_ERROR,
                        f"Duplicate class name {item[1]}",
                        item[0].line_num,
                    )
                self.template_class_index[item[1]] = TemplateClassDef(item, self)

    # [class classname inherits superclassname [items]]
    def __add_all_class_types_to_type_manager(self, parsed_program) -> None:
        self.type_manager: TypeManager = TypeManager()
        for item in parsed_program:
            if item[0] == InterpreterBase.CLASS_DEF:
                class_name: str = item[1]
                superclass_name: Optional[str] = None
                if item[2] == InterpreterBase.INHERITS_DEF:
                    superclass_name = item[3]
                self.type_manager.add_class_type(class_name, superclass_name)
