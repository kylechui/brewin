include Types

let program_source =
  let rec read_from_stdin lines =
    try
      let line = input_line stdin in
      read_from_stdin (line :: lines)
    with End_of_file -> List.rev lines
  in
  read_from_stdin []

(* TODO: Figure out how to make this a linear time scan *)
(* Maybe reverse scan? But would require suffix-free encodings *)
(* Since the grammar is not a prefix-free encoding, we should split on token
   boundaries first; e.g. parens, whitespace, !=, ==, strings, etc. *)
let token_of_string : string -> token = function
  | "begin" -> `BEGIN_DEF
  | "bool" -> `BOOL_DEF
  | "call" -> `CALL_DEF
  | ")" -> `CLOSE_PAREN_DEF
  | "class" -> `CLASS_DEF
  | "#" -> `COMMENT_CHAR_DEF
  | "false" -> `FALSE_DEF
  | "field" -> `FIELD_DEF
  | "if" -> `IF_DEF
  | "inputi" -> `INPUT_INT_DEF
  | "inputs" -> `INPUT_STRING_DEF
  | "int" -> `INT_DEF
  | "let" -> `LET_DEF
  | "main" -> `MAIN_DEF
  | "method" -> `METHOD_DEF
  | "me" -> `ME_DEF
  | "new" -> `NEW_DEF
  | "null" -> `NULL_DEF
  | "(" -> `OPEN_PAREN_DEF
  | "print" -> `PRINT_DEF
  | "\"" -> `QUOTE_CHAR
  | "return" -> `RETURN_DEF
  | "set" -> `SET_DEF
  | "string" -> `STRING_DEF
  | "true" -> `TRUE_DEF
  | "void" -> `VOID_DEF
  | "while" -> `WHILE_DEF
  | id -> `Identifier id

let string_of_token : token -> string = function
  | `BEGIN_DEF -> "begin"
  | `BOOL_DEF -> "bool"
  | `CALL_DEF -> "call"
  | `CLOSE_PAREN_DEF -> ")"
  | `CLASS_DEF -> "class"
  | `COMMENT_CHAR_DEF -> "#"
  | `FALSE_DEF -> "false"
  | `FIELD_DEF -> "field"
  | `IF_DEF -> "if"
  | `INPUT_INT_DEF -> "inputi"
  | `INPUT_STRING_DEF -> "inputs"
  | `INT_DEF -> "int"
  | `LET_DEF -> "let"
  | `MAIN_DEF -> "main"
  | `METHOD_DEF -> "method"
  | `ME_DEF -> "me"
  | `NEW_DEF -> "new"
  | `NULL_DEF -> "null"
  | `OPEN_PAREN_DEF -> "("
  | `PRINT_DEF -> "print"
  | `QUOTE_CHAR -> "\""
  | `RETURN_DEF -> "return"
  | `SET_DEF -> "set"
  | `STRING_DEF -> "string"
  | `TRUE_DEF -> "true"
  | `VOID_DEF -> "void"
  | `WHILE_DEF -> "while"
  | `Identifier id -> id

(* FIXME: Does not handle case where delimiters appear inside quotes!! *)
let rec split_line' strs str = function
  | "" -> str :: strs |> List.filter (fun s -> String.length s != 0) |> List.rev
  | line ->
      let head = String.get line 0 in
      let tail = String.sub line 1 (String.length line - 1) in
      let str' = str ^ String.make 1 head in
      let in_string = String.starts_with str ~prefix:"\"" in
      if String.ends_with str' ~suffix:"\"" then
        if in_string then
          (* String.ends_with str' ~suffix:"\"" *)
          split_line' (str' :: strs) "" tail
        else split_line' strs str' tail
      else if String.ends_with str' ~suffix:" " then
        split_line' (str :: strs) "" tail
      else if String.ends_with str' ~suffix:"(" then
        split_line' (str :: "(" :: strs) "" tail
      else if String.ends_with str' ~suffix:")" then
        split_line' (")" :: str :: strs) "" tail
      else split_line' strs str' tail

let split_line = split_line' [] ""

let tokens =
  let tokenize_line line = List.map token_of_string (split_line line) in
  List.fold_left
    (fun tokens line -> tokens @ tokenize_line line)
    [] program_source
