include Brewin

let tokens = Lexer.tokens
let () = tokens |> List.map Lexer.string_of_token |> List.iter print_endline
