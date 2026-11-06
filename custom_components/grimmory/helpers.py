# Copyright (C) 2026 Michiel Cornelissen
# This file is part of ha-grimmory
# SPDX-License-Identifier: GPL-3.0-only
"""Helper functions for Grimmory."""

from typing import Any


def _get_book_device_name(book: dict[str, Any], book_id: int) -> str:
    """Build a device name from book metadata."""

    metadata = book.get("metadata")
    if metadata is None:
        return f"Book {book_id}"

    return f"{', '.join(metadata['authors'])} - {metadata['title']}"
