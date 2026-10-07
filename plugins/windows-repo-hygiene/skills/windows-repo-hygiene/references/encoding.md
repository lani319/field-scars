# Encodings and byte-order marks

## Windows PowerShell 5.1 needs a BOM for non-ASCII scripts

`powershell.exe` (5.1, still the default on many machines and servers) assumes a script without a BOM is in the
system ANSI code page (CP949 on Korean Windows, CP932 Japanese, CP1252 Western...). UTF-8 multi-byte characters are
then mis-decoded; in double-byte code pages a trailing byte can swallow the following ASCII quote. The string never
closes, and the parser reports errors such as:

- `The string is missing the terminator: "`
- `Unexpected token '...' in expression or statement`
- `Missing closing '}' in statement block`

...often many lines below the real culprit, which makes it look like a syntax problem. It is not.

Fix: save with UTF-8 **with BOM** (or UTF-16 LE). `encoding_check.py --fix` adds the BOM. To verify a script parses:

```powershell
$err = $null
[System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$null, [ref]$err) | Out-Null
$err.Count   # 0 = parses
```

PowerShell 7 (`pwsh`) defaults to UTF-8 and does not need the BOM, but a BOM does not hurt it - keep it if any
5.1 host may run the script.

Many tools (including AI agents' file-writing tools) create new files as UTF-8 without BOM. Editing an existing file
in place usually preserves its BOM; creating a new `.ps1` does not add one.

## Files that must NOT have a BOM

| File | What happens with a BOM |
|---|---|
| shell scripts / any `#!` file | the kernel does not see `#!`; "not found" or wrong interpreter |
| `.json` | strict parsers (JSON spec, many languages) reject byte 0 |
| `.env` | first variable name gets an invisible prefix and is never found |
| nginx configs | `unknown directive "﻿user"` |

Keep non-ASCII text in such files to comments, saved as UTF-8 without BOM.

## Mojibake in API tests is usually the client, not the data

Windows PowerShell 5.1's `Invoke-RestMethod` / `Invoke-WebRequest` may decode a response body in the ANSI code page
even when the server sends `charset=utf-8`. Symptom: you POST a Korean string, read it back, and the comparison
fails - but ASCII fields match. It is tempting to start suspecting database collation, `NVARCHAR` vs `VARCHAR`, or the
driver. Check the decoding first:

```powershell
$r = Invoke-WebRequest -Uri $url -UseBasicParsing
$json = [Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) | ConvertFrom-Json
```

If the comparison now passes, the data was always fine. Console output has the same problem: garbled characters in a
terminal are not evidence of corrupted storage.

## Legacy code-page files

`NOT_UTF8` means the bytes are not valid UTF-8. Do not batch-convert: confirm the actual encoding (open in an editor
that shows it, or try decoding with the expected code page), convert deliberately, and commit the conversion alone.
