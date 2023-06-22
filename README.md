# `Brewin` Interpreter

An interpreter for the [`Brewin`
language](https://docs.google.com/document/d/1pPQ2qZKbbsbZGBSwvuy1Ir-NZLPMgVt95WPQuI5aPho/edit#),
written in OCaml. The main goals of this project are:

- Interpret `Brewin` source code _unambiguously_
  - Fully specify the language
- Improve _correctness_ of the interpreter
  - Encode extra information into OCaml's rich type system

## Syntax

The grammar below uses the following meta-notation:

- Non-terminal symbols are written in $\textit{this font}$
- Terminal symbols are written in $\texttt{this font}$, except:
  - $\langle\texttt{INT\\_LITERAL}\rangle$ indicates a string matching the
    regular expression `-?[0-9]+`
  - $\langle\texttt{STRING\\_LITERAL}\rangle$ indicates a string of zero or more
    [ASCII characters](https://en.wikipedia.org/wiki/ASCII)
  - $\langle\texttt{IDENTIFIER}\rangle$ indicates a string matching the regular
    expression `[_a-zA-Z]+[_a-zA-Z0-9]*`
- Subscripts are used to differentiate between meta-variables
- A $\texttt *$ suffix is used to denote zero or more instances of the previous
  symbol

$$
\begin{align*}
  \textit p &\Coloneqq \textit c\texttt * \tag{Program} \\
  \textit c &\Coloneqq \texttt{(class}\ \textit{id}\ \textit f\texttt *\ \textit m\texttt *\texttt{)} \tag{Class} \\
  \textit f &\Coloneqq \texttt{(field}\ \textit{id}\ \textit v\texttt{)} \tag{Field} \\
  \textit m &\Coloneqq \texttt{(method}\ \textit{id}\ \texttt{(}\textit{id}\texttt *\texttt{)}\ \textit s\texttt{)} \tag{Method} \\
  \textit s &\Coloneqq \texttt{(print}\ \textit e\texttt*\texttt{)}\tag{Statement} \\
            &\mid \texttt{(set ...)} \\
            &\mid \texttt{(inputi ...)} \\
            &\mid \texttt{(inputs ...)} \\
            &\mid \texttt{TODO: Add other statements} \\
  \textit e &\Coloneqq \textit v \tag{Expression} \\
            &\mid \textit{id} \\
            &\mid\texttt{(!}\ \textit{id}\texttt{)} \\
            &\mid\texttt{(new}\ \textit{id}\texttt{)} \\
            &\mid\texttt{(+}\ \textit{id}_1\ \textit{id}_2\texttt{)} \\
            &\mid\texttt{(-}\ \textit{id}_1\ \textit{id}_2\texttt{)} \\
            &\mid\texttt{(*}\ \textit{id}_1\ \textit{id}_2\texttt{)} \\
            &\mid\texttt{(/}\ \textit{id}_1\ \textit{id}_2\texttt{)} \\
            &\mid\texttt{(\%}\ \textit{id}_1\ \textit{id}_2\texttt{)} \\
            &\mid\texttt{(==}\ \textit{id}_1\ \textit{id}_2\texttt{)} \\
            &\mid\texttt{(!=}\ \textit{id}_1\ \textit{id}_2\texttt{)} \\
            &\mid\texttt{(<}\ \textit{id}_1\ \textit{id}_2\texttt{)} \\
            &\mid\texttt{(<=}\ \textit{id}_1\ \textit{id}_2\texttt{)} \\
            &\mid\texttt{(>}\ \textit{id}_1\ \textit{id}_2\texttt{)} \\
            &\mid\texttt{(>=}\ \textit{id}_1\ \textit{id}_2\texttt{)} \\
            &\mid\texttt{(call}\ \textit e\ \textit{id}\ \textit e\texttt *\texttt{)} \\
  \textit v &\Coloneqq \texttt{null}\mid \texttt{true}\mid \texttt{false}\mid \langle\texttt{INT\_LITERAL}\rangle\mid \texttt{"}\langle\texttt{STRING\_LITERAL}\rangle\texttt{"}\tag{Value} \\
  \textit{id} &\Coloneqq \langle\texttt{IDENTIFIER}\rangle
\end{align*}
$$
