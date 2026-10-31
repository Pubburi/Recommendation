"""Extract the legacy seed's literal t_product rows without executing any SQL."""

import re
from decimal import Decimal

from pubburi_recommendation.catalog_audit import AuditError

COLUMNS = {"name", "type", "price", "img", "abv", "order_count"}
IDENTIFIER = r"`?[A-Za-z_][A-Za-z_0-9]*`?"
TARGET = rf"{IDENTIFIER}(?:\s*\.\s*{IDENTIFIER})?"
INSERT_TARGET = re.compile(
    rf"^INSERT\s+(?:(?:LOW_PRIORITY|DELAYED|HIGH_PRIORITY|IGNORE)\s+)*"
    rf"(?:INTO\s+)?({TARGET})(?=\s|\(|$)",
    re.I,
)
INSERT_LITERAL = re.compile(
    r"^INSERT\s+INTO\s+`?t_product`?\s*\(([^()]*)\)\s+VALUES\s+(.+)$",
    re.I | re.S,
)
NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")


def statements(sql: str):
    current = []
    index = 0
    while index < len(sql):
        character = sql[index]
        if character in "'\"`":
            quote = character
            start = index
            index += 1
            while index < len(sql):
                if sql[index] == "\\":
                    index += 2
                elif sql[index] == quote:
                    index += 1
                    if index < len(sql) and sql[index] == quote:
                        index += 1
                    else:
                        break
                else:
                    index += 1
            else:
                raise AuditError("unterminated_sql_quote")
            current.append(sql[start:index])
            continue
        if character == "#" or (
            sql.startswith("--", index) and (index + 2 == len(sql) or sql[index + 2].isspace())
        ):
            newline = sql.find("\n", index)
            index = len(sql) if newline == -1 else newline + 1
            current.append(" ")
            continue
        if sql.startswith("/*", index):
            if sql.startswith(("/*!", "/*+"), index):
                raise AuditError("executable_or_hint_comments_not_supported")
            end = sql.find("*/", index + 2)
            if end == -1 or "/*" in sql[index + 2 : end]:
                raise AuditError("unterminated_or_nested_sql_comment")
            current.append(" ")
            index = end + 2
            continue
        if character == ";":
            statement = "".join(current).strip()
            if statement:
                yield statement
            current = []
        else:
            current.append(character)
        index += 1
    if "".join(current).strip():
        raise AuditError("unterminated_sql_statement")


def literal_rows(source: str, column_count: int) -> list[list]:
    index = 0

    def whitespace():
        nonlocal index
        while index < len(source) and source[index].isspace():
            index += 1

    def expect(character):
        nonlocal index
        whitespace()
        if index >= len(source) or source[index] != character:
            raise AuditError("unsupported_product_values_syntax")
        index += 1

    def value():
        nonlocal index
        whitespace()
        if index < len(source) and source[index] == "'":
            index += 1
            result = []
            while index < len(source):
                character = source[index]
                index += 1
                if character == "\\":
                    raise AuditError("product_backslash_strings_not_supported")
                if character == "'":
                    if index < len(source) and source[index] == "'":
                        result.append("'")
                        index += 1
                    else:
                        return "".join(result)
                else:
                    result.append(character)
            raise AuditError("unterminated_product_string")
        if source[index : index + 4].upper() == "NULL":
            index += 4
            return None
        number = NUMBER.match(source, index)
        if number is None:
            raise AuditError("product_values_require_supported_literals")
        index = number.end()
        return Decimal(number.group())

    rows = []
    while True:
        expect("(")
        row = []
        for position in range(column_count):
            if position:
                expect(",")
            row.append(value())
        expect(")")
        rows.append(row)
        if len(rows) > 2000:
            raise AuditError("seed_exceeds_2000_products")
        whitespace()
        if index == len(source):
            return rows
        expect(",")


def mask_string_literals(statement: str) -> str:
    """Keep SQL identifiers/keywords while hiding string values from mutation detection."""
    result = []
    index = 0
    while index < len(statement):
        if statement[index] not in "'\"`":
            result.append(statement[index])
            index += 1
            continue
        quote = statement[index]
        start = index
        index += 1
        while index < len(statement):
            if statement[index] == "\\":
                index += 2
            elif statement[index] == quote:
                index += 1
                if index < len(statement) and statement[index] == quote:
                    index += 1
                else:
                    break
            else:
                index += 1
        result.append(statement[start:index] if quote == "`" else " ")
    return "".join(result)


def extract_products(sql: str) -> tuple[list[dict], int]:
    products = []
    inserts = 0
    for statement in statements(sql):
        target = INSERT_TARGET.match(statement)
        if target is None:
            masked = mask_string_literals(statement)
            mutation = re.match(
                r"^(?:UPDATE|REPLACE|DELETE|TRUNCATE|ALTER|DROP|LOAD)\b", masked, re.I
            )
            if re.match(r"^WITH\b", masked, re.I):
                mutation = re.search(r"\b(?:UPDATE|REPLACE|DELETE|INSERT)\b", masked, re.I)
            # Conservative for unsupported joined/CTE/load mutations; values aren't identifiers.
            if mutation and re.search(
                r"(?<![A-Za-z_0-9])`?t_product`?(?![A-Za-z_0-9])", masked, re.I
            ):
                raise AuditError("non_insert_product_mutation_not_supported")
            continue
        if target.group(1).replace("`", "").split(".")[-1].strip().lower() != "t_product":
            continue
        match = INSERT_LITERAL.fullmatch(statement)
        if match is None:
            raise AuditError("only_explicit_product_literal_inserts_supported")
        raw_columns = [column.strip() for column in match.group(1).split(",")]
        if any(re.fullmatch(IDENTIFIER, column) is None for column in raw_columns):
            raise AuditError("invalid_product_column_identifier")
        columns = [column.replace("`", "").lower() for column in raw_columns]
        if len(columns) != len(COLUMNS) or set(columns) != COLUMNS:
            raise AuditError("product_insert_columns_must_match_legacy_contract")
        rows = literal_rows(match.group(2), len(columns))
        products.extend(dict(zip(columns, row, strict=True)) for row in rows)
        inserts += 1
        if len(products) > 2000:
            raise AuditError("seed_exceeds_2000_products")
    if not products:
        raise AuditError("no_active_product_literal_rows")
    return products, inserts
