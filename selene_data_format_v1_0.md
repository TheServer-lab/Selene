# Selene Data Format — Version 1.0 Specification

> **Status:** Draft — v1.0

---

## Overview

Selene is a compact, human-readable data serialization format designed for configuration files and simple data interchange. It favors minimal punctuation, consistent syntax, and easy parsing.

### Design goals
- One rule for key/value pairs everywhere: `key: value`
- Records delimited by `{ }`, blocks delimited by `[ ]`
- No terminator punctuation — structure comes from delimiters alone
- Explicit versioning baked into the format
- Trivially parsable

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

A block is a named, ordered collection of records:

```
block_name [
    <record>*
]
```

- Block names follow identifier rules (see Lexical rules).
- Blocks may appear in any order.
- Comments and blank lines are allowed anywhere between or within blocks.

---

## Records

A **record** is a set of `key: value` fields enclosed in `{ }`:

```
{ key: value  key: value  ... }
```

Records may be written on one line or spread across multiple lines — whitespace is insignificant:

```
{
    name: "Rick"
    age: 43
}
```

Both forms are equivalent. Multi-line is preferred for records with many fields.

---

## Fields

Every field follows the same rule without exception:

```
identifier : value
```

This applies at every level, including nested objects. There is no special syntax for any value type.

Duplicate keys within the same record are **illegal**. A parser **must** reject any record where the same key appears more than once. This applies at every nesting level independently — a key may be reused across different records or different nested objects, but never twice within the same `{ }`.

---

## Lexical rules

### Identifiers
Keys and block names consist of ASCII letters, digits, `_`, and `-`, beginning with a letter or `_`:

```
[A-Za-z_][A-Za-z0-9_-]*
```

Identifiers are case-sensitive.

### Strings
String values **must** be double-quoted:

```
name: "Rick"
bio:  "Line one\nLine two"
```

Supported escape sequences: `\n`, `\t`, `\\`, `\"`

### Numbers
- **Integer:** optional leading `-` followed by one or more digits. Example: `43`, `-4`
- **Float:** digits, one decimal point, one or more fractional digits. Example: `19.5`, `999.99`, `3.0`

A float **must** have at least one digit after the decimal point.

### Booleans and null
`true`, `false`, and `null` are reserved lowercase keywords.

### Unquoted tokens
Only numbers, booleans, and `null` may appear unquoted. All other values **must** be quoted strings.

### Comments
`#` begins a comment that runs to the end of the line:

```
# full line comment
{ name: "Rick"  age: 43 }  # inline comment
```

### Whitespace
Spaces, tabs, and newlines are insignificant outside quoted strings. Both LF and CRLF line endings are accepted.

---

## Nested objects

A nested object is a value like any other — it follows the same `key: value` rule:

```
{ name: "Rick"  age: 43  address: { city: "London"  zip: "12345" } }
```

Nested objects may be nested to any depth. There is no special syntax at any level.

---

## No array primitive

Selene has no inline array type. Ordered collections are expressed as blocks. This is a deliberate design choice: all collection entries are structured records rather than anonymous values.

---

## Examples

### Simple block

```
__sel_v1__

users [
    { name: "Rick"  age: 43 }
    { name: "Sam"   age: 56 }
    { name: "Ilsa"  age: 27 }
]
```

### Multiple blocks

```
__sel_v1__

users [
    { name: "Rick"  age: 43 }
    { name: "Sam"   age: 56 }
]

products [
    { name: "Laptop"  price: 999.99 }
    { name: "Mouse"   price: 19.5   }
]
```

### Nested objects

```
__sel_v1__

users [
    {
        name: "Rick"
        age: 43
        address: {
            city: "London"
            zip: "12345"
        }
    }
    {
        name: "Sam"
        age: 56
        address: {
            city: "Paris"
            zip: "75001"
        }
    }
]
```

### Converted to JSON

```json
{
  "users": [
    { "name": "Rick", "age": 43, "address": { "city": "London", "zip": "12345" } },
    { "name": "Sam",  "age": 56, "address": { "city": "Paris",  "zip": "75001" } }
  ]
}
```

---

## EBNF grammar

```ebnf
file        ::= header block*
header      ::= "__sel_v1__" newline

block       ::= identifier "[" record* "]"
record      ::= "{" field* "}"
field       ::= identifier ":" value

value       ::= quoted-string | number | boolean | null | record

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

The grammar is intentionally small. Whitespace and comments are stripped by the tokenizer before parsing.

---

## JSON ↔ Selene conversion

| Selene | JSON |
|---|---|
| `block_name [ ... ]` | `"block_name": [ ... ]` |
| `{ fields }` | `{ ... }` |
| Nested `{ ... }` | Nested JSON object |
| `true` / `false` / `null` | JSON boolean / null |
| Quoted string | JSON string |
| Integer / float | JSON number |

---

## Parsing advice

- **Tokenize first, then parse.** Strip comments and normalise whitespace early. The grammar is then straightforward to implement as a recursive descent parser.
- **Emit contextual errors.** Unexpected EOF inside `{` or `[` should name the block and field being parsed if known.
- **Accept both line endings.** Normalise CRLF to LF early in the pipeline.

---

## Versioning

- Files **must** begin with `__sel_v1__`.
- Parsers **must** reject files with missing or unknown version headers.
- Future versions use the same header pattern: `__sel_v2__`, etc.

---

## Quick reference

```
Version header : __sel_v1__
Comment        : # text
Block          : name [ records ]
Record         : { key: value  key: value }
Nested object  : key: { key: value }
Strings        : always double-quoted
Numbers        : 43  -4  19.5  999.99
Booleans/null  : true  false  null
```

---

## Changelog

- v1.0 — initial specification.

---

*End of specification.*
