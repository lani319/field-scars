# Shell quoting traps for agents on Windows

AI coding agents on Windows often drive two shells: a POSIX shell (Git Bash) and PowerShell. Both can alter text on
its way into a file or a command without any error.

## Heredocs are not always literal

In theory `cat > f <<'EOF'` writes the body verbatim. In practice, when the command string is itself produced and
passed through another layer (an agent's tool call, an IDE, a wrapper script), backslash sequences may already be
collapsed before the shell sees them:

- `"\\n"` intended as "backslash + n" inside Python source arrives as a real newline;
- a regex `\\s` arrives as `\s` - Python warns, keeps running, and the pattern still looks plausible;
- long bodies with mixed quotes end in `unexpected EOF while looking for matching '`.

Rule: anything containing backslashes - regular expressions, Windows paths, escape sequences, source code - goes into
files through a file-writing tool, not through a heredoc or `echo`. Commit messages and plain prose are usually fine.

If a script must apply text edits, put the edits in a data file (JSON) and let a program read it -
`safe_replace.py` exists for this.

## Windows PowerShell 5.1 specifics

- `&&` and `||` do not exist (parser error). Use `A; if ($?) { B }`.
- `2>&1` on a native executable wraps every stderr line in an error record and sets `$?` to false even on exit 0.
- `Set-Content` / `Add-Content` default to the ANSI code page; `Out-File` / `>` to UTF-16 or UTF-8 with BOM depending
  on version. Pass `-Encoding utf8` deliberately, and remember 5.1's `utf8` means *with* BOM.
- Double-quoted strings expand `$var` and backticks; use single-quoted here-strings (`@' ... '@`, closing `'@` at
  column 0) for literal text.

## Paths

- Prefer forward slashes in tool arguments; most Windows programs accept them, and they survive shells unchanged.
- Quote paths with spaces. In PowerShell, call an executable path with spaces via `& "C:\Program Files\x\x.exe"`.
- In code, build paths with the language's path library instead of string concatenation.
