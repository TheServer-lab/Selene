"""
selene.py — Selene Data Format v1.0
Parser, validator, and converter.

Public API:
    loads(text)        Parse a Selene string → dict
    load(fp)           Parse a Selene file object → dict
    dumps(data)        Serialize a dict → Selene string
    dump(data, fp)     Serialize a dict → Selene file object
    validate(text)     Validate a Selene string → raises SeleneError on failure
    to_json(text)      Convert Selene string → JSON string
    from_json(text)    Convert JSON string → Selene string
"""

import re
import json
from typing import Any


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SeleneError(Exception):
    """Raised on any parse, validation, or serialization error."""


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

TK_HEADER = "HEADER"
TK_IDENT  = "IDENT"
TK_COLON  = "COLON"
TK_LBRACE = "LBRACE"
TK_RBRACE = "RBRACE"
TK_LBRACK = "LBRACK"
TK_RBRACK = "RBRACK"
TK_STRING = "STRING"
TK_FLOAT  = "FLOAT"
TK_INT    = "INT"
TK_BOOL   = "BOOL"
TK_NULL   = "NULL"
TK_EOF    = "EOF"

_TOKEN_PATTERNS = [
    (TK_HEADER, r"__sel_v1__"),
    (TK_BOOL,   r"(?:true|false)(?![A-Za-z0-9_\-])"),
    (TK_NULL,   r"null(?![A-Za-z0-9_\-])"),
    (TK_FLOAT,  r"-?\d+\.\d+"),
    (TK_INT,    r"-?\d+"),
    (TK_STRING, r'"(?:[^"\\]|\\.)*"'),
    (TK_IDENT,  r"[A-Za-z_][A-Za-z0-9_\-]*"),
    (TK_COLON,  r":"),
    (TK_LBRACE, r"\{"),
    (TK_RBRACE, r"\}"),
    (TK_LBRACK, r"\["),
    (TK_RBRACK, r"\]"),
]

_MASTER_RE = re.compile(
    "|".join(f"(?P<{name}>{pattern})" for name, pattern in _TOKEN_PATTERNS)
)

_ESCAPE_MAP = {"n": "\n", "t": "\t", "\\": "\\", '"': '"'}


class _Token:
    __slots__ = ("kind", "value", "line")

    def __init__(self, kind: str, value: str, line: int):
        self.kind  = kind
        self.value = value
        self.line  = line

    def __repr__(self):
        return f"Token({self.kind}, {self.value!r}, line={self.line})"


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[_Token]:
    text = text.replace("\r\n", "\n")
    tokens: list[_Token] = []
    line = 1
    i = 0
    length = len(text)

    while i < length:
        ch = text[i]

        # Whitespace
        if ch in " \t\n":
            if ch == "\n":
                line += 1
            i += 1
            continue

        # Comment
        if ch == "#":
            while i < length and text[i] != "\n":
                i += 1
            continue

        m = _MASTER_RE.match(text, i)
        if not m:
            raise SeleneError(f"Line {line}: unexpected character {ch!r}")

        kind  = m.lastgroup
        value = m.group()
        tokens.append(_Token(kind, value, line))
        line += value.count("\n")
        i = m.end()

    tokens.append(_Token(TK_EOF, "", line))
    return tokens


# ---------------------------------------------------------------------------
# String unescaping
# ---------------------------------------------------------------------------

def _unescape(s: str) -> str:
    """Strip surrounding quotes and resolve escape sequences."""
    inner = s[1:-1]
    result: list[str] = []
    i = 0
    while i < len(inner):
        if inner[i] == "\\":
            i += 1
            ch = inner[i]
            if ch not in _ESCAPE_MAP:
                raise SeleneError(f"Unknown escape sequence \\{ch}")
            result.append(_ESCAPE_MAP[ch])
        else:
            result.append(inner[i])
        i += 1
    return "".join(result)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class _Parser:
    def __init__(self, tokens: list[_Token]):
        self._tokens = tokens
        self._pos    = 0

    # --- token navigation ---------------------------------------------------

    def _peek(self) -> _Token:
        return self._tokens[self._pos]

    def _consume(self, kind: str | None = None) -> _Token:
        tok = self._tokens[self._pos]
        if kind and tok.kind != kind:
            raise SeleneError(
                f"Line {tok.line}: expected {kind}, got {tok.kind} ({tok.value!r})"
            )
        self._pos += 1
        return tok

    # --- grammar rules ------------------------------------------------------

    def parse_file(self) -> dict:
        if self._peek().kind != TK_HEADER:
            raise SeleneError(
                "File must begin with version header __sel_v1__"
            )
        self._consume(TK_HEADER)

        result: dict = {}
        while self._peek().kind != TK_EOF:
            name, records = self._parse_block()
            if name in result:
                raise SeleneError(f"Duplicate block name: {name!r}")
            result[name] = records

        return result

    def _parse_block(self) -> tuple[str, list]:
        name_tok = self._consume(TK_IDENT)
        name     = name_tok.value
        self._consume(TK_LBRACK)

        records: list[dict] = []
        while self._peek().kind != TK_RBRACK:
            if self._peek().kind == TK_EOF:
                raise SeleneError(
                    f"Line {name_tok.line}: unexpected EOF inside block {name!r}"
                )
            records.append(self._parse_record())

        self._consume(TK_RBRACK)
        return name, records

    def _parse_record(self, context: str = "record") -> dict:
        lbrace = self._consume(TK_LBRACE)
        record: dict = {}

        while self._peek().kind != TK_RBRACE:
            if self._peek().kind == TK_EOF:
                raise SeleneError(
                    f"Line {lbrace.line}: unexpected EOF inside {context}"
                )
            key_tok = self._consume(TK_IDENT)
            key     = key_tok.value

            if key in record:
                raise SeleneError(
                    f"Line {key_tok.line}: duplicate key {key!r} in record"
                )

            self._consume(TK_COLON)
            record[key] = self._parse_value(context=key)

        self._consume(TK_RBRACE)
        return record

    def _parse_value(self, context: str = "") -> Any:
        tok = self._peek()

        if tok.kind == TK_STRING:
            self._consume()
            return _unescape(tok.value)

        if tok.kind == TK_FLOAT:
            self._consume()
            return float(tok.value)

        if tok.kind == TK_INT:
            self._consume()
            return int(tok.value)

        if tok.kind == TK_BOOL:
            self._consume()
            return tok.value == "true"

        if tok.kind == TK_NULL:
            self._consume()
            return None

        if tok.kind == TK_LBRACE:
            return self._parse_record(context=f"nested object in {context!r}")

        raise SeleneError(
            f"Line {tok.line}: unexpected token {tok.kind} ({tok.value!r})"
            + (f" in field {context!r}" if context else "")
        )


# ---------------------------------------------------------------------------
# Serializer (dumps)
# ---------------------------------------------------------------------------

_ESCAPE_WRITE = str.maketrans({
    "\\": "\\\\",
    '"':  '\\"',
    "\n": "\\n",
    "\t": "\\t",
})

_MAX_LINE = 88  # soft limit for single-line records


def _escape_string(s: str) -> str:
    return f'"{s.translate(_ESCAPE_WRITE)}"'


def _serialize_value(value: Any, indent: int, level: int) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        s = repr(value)
        if "." not in s:
            s += ".0"
        return s
    if isinstance(value, str):
        return _escape_string(value)
    if isinstance(value, dict):
        # Inline the nested object (strip leading indent from _serialize_record)
        return _serialize_record(value, indent=indent, level=level).lstrip()
    raise SeleneError(
        f"Cannot serialize value of type {type(value).__name__!r}; "
        "expected str, int, float, bool, None, or dict."
    )


def _serialize_record(record: dict, indent: int, level: int) -> str:
    pad       = " " * (indent * level)
    inner_pad = " " * (indent * (level + 1))
    has_nested = any(isinstance(v, dict) for v in record.values())

    # Attempt single-line
    if not has_nested:
        fields = "  ".join(
            f"{k}: {_serialize_value(v, indent, level)}"
            for k, v in record.items()
        )
        single = f"{pad}{{ {fields} }}"
        if len(single) <= _MAX_LINE:
            return single

    # Multi-line
    lines = [f"{pad}{{"]
    for k, v in record.items():
        lines.append(f"{inner_pad}{k}: {_serialize_value(v, indent, level + 1)}")
    lines.append(f"{pad}}}")
    return "\n".join(lines)


def _serialize(data: dict, indent: int) -> str:
    out: list[str] = ["__sel_v1__", ""]
    for block_name, records in data.items():
        if not isinstance(records, list):
            raise SeleneError(
                f"Block {block_name!r} must be a list of dicts, got {type(records).__name__!r}"
            )
        out.append(f"{block_name} [")
        for record in records:
            if not isinstance(record, dict):
                raise SeleneError(
                    f"Records in block {block_name!r} must be dicts, got {type(record).__name__!r}"
                )
            out.append(_serialize_record(record, indent=indent, level=1))
        out.append("]")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def loads(text: str) -> dict:
    """
    Parse a Selene-formatted string and return a Python dict.

    Raises SeleneError on any syntax or validation error.
    """
    tokens = _tokenize(text)
    return _Parser(tokens).parse_file()


def load(fp) -> dict:
    """
    Read and parse a Selene file object and return a Python dict.

    Raises SeleneError on any syntax or validation error.
    """
    return loads(fp.read())


def dumps(data: dict, indent: int = 4) -> str:
    """
    Serialize a Python dict to a Selene-formatted string.

    The dict must have the shape:
        { "block_name": [ { "key": value, ... }, ... ], ... }

    Raises SeleneError if the data cannot be represented in Selene.
    """
    return _serialize(data, indent=indent)


def dump(data: dict, fp, indent: int = 4) -> None:
    """
    Serialize a Python dict and write it to a file object.

    Raises SeleneError if the data cannot be represented in Selene.
    """
    fp.write(dumps(data, indent=indent))


def validate(text: str) -> None:
    """
    Validate a Selene-formatted string.

    Returns None if valid. Raises SeleneError with a descriptive message
    on the first error found.
    """
    loads(text)  # parsing is validation; result is discarded


def to_json(text: str, **kwargs) -> str:
    """
    Parse a Selene string and return a JSON string.

    Extra keyword arguments are forwarded to json.dumps (e.g. indent=2).
    """
    return json.dumps(loads(text), **kwargs)


def from_json(text: str, indent: int = 4) -> str:
    """
    Parse a JSON string and return a Selene string.

    The JSON must be an object whose values are arrays of objects.
    Raises SeleneError if the JSON structure cannot be represented in Selene.
    """
    return dumps(json.loads(text), indent=indent)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli():
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        prog="selene",
        description="Selene v1.0 — validate, parse, and convert Selene files.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # validate
    p_val = sub.add_parser("validate", help="Validate a Selene file.")
    p_val.add_argument("file", help="Path to .sel file")

    # to-json
    p_toj = sub.add_parser("to-json", help="Convert Selene → JSON.")
    p_toj.add_argument("file", help="Path to .sel file")
    p_toj.add_argument("--indent", type=int, default=2)

    # from-json
    p_frj = sub.add_parser("from-json", help="Convert JSON → Selene.")
    p_frj.add_argument("file", help="Path to .json file")
    p_frj.add_argument("--indent", type=int, default=4)

    args = parser.parse_args()

    try:
        if args.command == "validate":
            with open(args.file, encoding="utf-8") as f:
                validate(f.read())
            print(f"OK: {args.file} is valid Selene v1.0")

        elif args.command == "to-json":
            with open(args.file, encoding="utf-8") as f:
                print(to_json(f.read(), indent=args.indent))

        elif args.command == "from-json":
            with open(args.file, encoding="utf-8") as f:
                print(from_json(f.read(), indent=args.indent))

    except SeleneError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _cli()
