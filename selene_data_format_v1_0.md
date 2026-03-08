# Selene Data Format — Version 1.0 Specification

> **Status:** Draft — v1.0

---

## Overview

Selene is a compact, human-readable data serialization format designed for configuration files and simple data interchange. Its guiding principle is that a file should read like structured prose: fields are statements, and records end with punctuation — either a period `.` (end of block) or a comma `,` (another record follows).

### Design goals
- Easy to read and edit by hand
- Unambiguous parsing with minimal punctuation
- Explicit versioning baked into the format
- No implicit structure — every record is explicitly terminated

---

## File layout

Every Selene file **must** begin with the version header on its own line, followed by zero or more blocks:

```
__sel_v1__

<block>*
```

A parser **must** reject any file with a missing or unrecognised version header.

---

## Blocks

A block is a named collection of records:

```
block_name[
    <record>*
]
```

- Block names follow identifier rules (see Lexical rules).
- Blocks may appear in any order.
- Comments and blank lines are allowed anywhere between blocks or records.

---

## Records and fields

A **record** is an ordered set of `key: value` fields. Fields are written one per line:

```
name: "Rick"
age: 26,
```

A new field header (i.e. any line beginning with `identifier:`) implicitly closes the previous field. Records are explicitly terminated by a **record terminator** suffix on the last field's value (see Record termination).

### Field syntax

```
field  →  identifier ':' value
value  →  quoted-string | number | boolean | null | object
```

---

## Lexical rules

### Identifiers
Keys and block names are ASCII letters, digits, `_`, and `-`, beginning with a letter or `_`:

```
[A-Za-z_][A-Za-z0-9_-]*
```

Identifiers are case-sensitive.

### Strings
All string values **must** be double-quoted:

```
name: "Rick"
bio:  "Line one\nLine two"
```

Supported escape sequences inside quoted strings: `\n`, `\t`, `\\`, `\"`.

### Numbers
- **Integer:** an optional leading `-` followed by digits. Example: `26`, `-4`
- **Float:** digits, one decimal point, one or more fractional digits. Example: `19.5`, `999.99`, `3.0`

A float **must** have at least one digit after the decimal point. The decimal point is only meaningful inside a numeric literal when followed immediately by a digit.

### Booleans and null
`true`, `false`, and `null` are reserved lowercase keywords.

### Unquoted tokens
Only numbers, booleans, and `null` may appear unquoted. Everything else **must** be quoted. This rule exists to keep tokenization unambiguous.

### Comments
`#` begins a comment that runs to the end of the line. Comments may appear on their own line or after any field:

```
# This is a comment
name: "Rick"   # inline comment
```

### Whitespace
Spaces and tabs are insignificant outside quoted strings. Both LF and CRLF line endings are accepted.

---

## Record termination

A record terminator is a **single-character suffix** appended directly to the last field's value — no space between the value and the terminator:

| Terminator | Meaning |
|---|---|
| `,` | This record ends; another record follows in this block. |
| `.` | This record ends; it is the last record in this block. |

Every record **must** be explicitly terminated. A parser **must** reject a block where any record lacks a terminator.

These rules are bidirectionally enforced:

- A record terminated with `,` **must** be followed by another record. A `,` on the last record in a block is an error.
- A record terminated with `.` **must** be the final record in the block. A `.` on any record that is followed by another record is an error.

### Examples

```
__sel_v1__

users[
    name: "Rick"
    age: 26,
    name: "Sam"
    age: 19.
]

products[
    name: "Laptop"
    price: 999.99,
    name: "Mouse"
    price: 19.5.
]
```

- `age: 26,` — Rick's record ends; Sam's follows.
- `age: 19.` — Sam's record ends; no more records in `users`.
- `price: 19.5.` — The float is `19.5`; the trailing `.` is the record terminator.

### Disambiguating floats and terminators

The parser must distinguish between a decimal point inside a float and a record-terminating `.`:

- If `.` is **followed immediately by a digit**, it is part of a float: `19.5`
- If `.` is **not followed by a digit** (end of token, whitespace, or comment follows), it is the record terminator: `19.`
- `19.5.` — tokenises as float `19.5` followed by record terminator `.`

Implementations must handle this in the tokenizer, not in the grammar layer.

---

## Nested objects

Use `{ ... }` to embed a nested object within a field:

```
identifier{
    field: value
    ...
}
```

The record terminator is placed on the **closing brace** of the outermost nested object when the object is the last field of the record:

| Suffix | Meaning |
|---|---|
| `},` | Nested object closes; another record follows. |
| `}.` | Nested object closes; last record in block. |

### Example

```
__sel_v1__

users[
    name: "Rick"
    age: 26
    address{
        city: "London"
        zip: "12345"
    },
    name: "Sam"
    age: 19.
]
```

Converted to JSON:

```json
{
  "users": [
    { "name": "Rick", "age": 26, "address": { "city": "London", "zip": "12345" } },
    { "name": "Sam", "age": 19 }
  ]
}
```

Nested objects may be nested further. The terminator always lives on the outermost closing brace of the record's final field.

---

## No array primitive

Selene has no inline array type. Ordered collections are expressed as blocks. This is a deliberate design choice: it forces all collection entries to be named, structured records rather than anonymous values.

---

## EBNF grammar

```ebnf
file        ::= header block*
header      ::= "__sel_v1__" newline

block       ::= identifier "[" record* "]"
record      ::= field* terminal-field
field       ::= identifier ":" value newline
terminal-field ::= identifier ":" terminal-value newline
               | identifier object-terminated

value       ::= quoted-string | number | boolean | null | object
terminal-value ::= (quoted-string | number | boolean | null) ("," | ".")

object      ::= "{" field* "}"
object-terminated ::= "{" field* "}" ("," | ".")

quoted-string ::= '"' (escape | [^"\\])* '"'
escape        ::= "\\" [nt\\"]
number        ::= integer | float
integer       ::= "-"? digit+
float         ::= "-"? digit+ "." digit+
boolean       ::= "true" | "false"
null          ::= "null"
identifier    ::= [A-Za-z_][A-Za-z0-9_-]*
digit         ::= [0-9]
newline       ::= "\n" | "\r\n"
```

---

## JSON ↔ Selene conversion

| Selene construct | JSON equivalent |
|---|---|
| `block_name[ ... ]` | `"block_name": [ ... ]` |
| Record `{ fields }` | JSON object `{ ... }` |
| Nested `{ ... }` | Nested JSON object |
| `true` / `false` / `null` | JSON boolean / null |
| Quoted string | JSON string |
| Integer / float | JSON number |

---

## Parsing advice

- **Tokenize first, then parse.** The `.` disambiguation (float vs terminator) must be handled in the tokenizer by looking at the character immediately after the `.`.
- **Reject on missing terminator.** If `]` is reached and the last record has no `.` or `},` / `}.`, emit an error.
- **Emit contextual errors.** Unexpected EOF inside `{` or `[` should name the block and, if known, the field being parsed.
- **Accept both line endings.** Normalise CRLF to LF early in the pipeline.

---

## Versioning

- Files **must** begin with `__sel_v1__`.
- Parsers **must** reject files with missing or unknown version headers.
- Future versions use the same header pattern: `__sel_v2__`, etc.

---

## Quick reference

```
Version header  : __sel_v1__
Comment         : # text
Block           : name[ records ]
Record fields   : key: value
Nested object   : key{ fields }
Record separator: , (suffix on last value or })
Record terminator: . (suffix on last value or })
Strings         : always double-quoted
Numbers         : 26  -4  19.5  999.99
Booleans / null : true  false  null
```

---

## Changelog

- v1.0 — initial specification.

---

*End of specification.*
