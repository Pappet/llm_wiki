"""
constants.py — Primitive Konstanten des Wiki-Processors.
Layer 0: keine wiki_lib-Imports.
"""

IMAGE_MIME_MAP = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}

ENTITY_TYPES = {"tool", "model", "concept", "project", "person"}
MAX_ENTITIES_PER_NOTE = 10
ENTITY_FUZZY_CUTOFF = 0.85
TOPIC_FUZZY_CUTOFF = 0.75
DESCRIPTION_MAX_CHARS = 500

RESERVED_WIKI_FILES = {"index.md", "log.md"}

# Heading-Konstanten — werden in entities.py, secondary.py und linter.py verwendet
MENTIONS_HEADING = "## Erwähnt in"
SECONDARY_MENTIONS_HEADING = "## Erwähnungen"

AUTO_APPLICABLE_KINDS = {
    "duplicate_content",
    "redundant_paragraphs",
    "malformed_list",
    "section_misplaced",
}
