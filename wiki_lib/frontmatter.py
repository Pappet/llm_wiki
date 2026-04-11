"""
frontmatter.py — Minimaler YAML-Frontmatter-Parser (kein PyYAML).
Layer 1: keine wiki_lib-Imports.

Exports: parse_frontmatter, serialize_frontmatter
"""

import re


def parse_frontmatter(content):
    """
    Parst YAML-artiges Frontmatter. Unterstützt: strings, ints, booleans, leere Listen [].
    Returns: (dict, body_str). Wenn kein Frontmatter: ({}, content).
    """
    if not content.startswith("---"):
        return {}, content
    end = content.find("\n---", 3)
    if end < 0:
        return {}, content
    header = content[3:end].strip()
    body_start = end + 4
    if body_start < len(content) and content[body_start] == "\n":
        body_start += 1
    body = content[body_start:]

    fm = {}
    for line in header.splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$', line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val == "" or val == "[]":
            fm[key] = [] if val == "[]" else ""
        elif val.lower() in ("true", "false"):
            fm[key] = (val.lower() == "true")
        elif re.match(r'^-?\d+$', val):
            fm[key] = int(val)
        else:
            if (val.startswith('"') and val.endswith('"')) or \
               (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            fm[key] = val
    return fm, body


def serialize_frontmatter(fm, body):
    """Serialisiert Frontmatter-Dict zurück in Markdown mit --- Delimitern."""
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
            else:
                items = ", ".join(f'"{x}"' for x in v)
                lines.append(f"{k}: [{items}]")
        elif isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, int):
            lines.append(f"{k}: {v}")
        else:
            s = str(v)
            if any(c in s for c in ':#\'"') or s != s.strip():
                s = '"' + s.replace('"', '\\"') + '"'
            lines.append(f"{k}: {s}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines) + body
