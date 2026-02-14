"""File I/O, text processing, and packaging utilities."""

import json
import os
import re
import zipfile
from pathlib import Path
from typing import Any


def read_transcript(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def read_all_transcripts(paths: list[str]) -> list[dict]:
    results = []
    for p in paths:
        try:
            content = read_transcript(p)
            results.append({
                "filename": os.path.basename(p),
                "path": p,
                "content": content,
                "word_count": len(content.split()),
            })
        except Exception as e:
            results.append({"filename": os.path.basename(p), "path": p,
                           "content": "", "word_count": 0, "error": str(e)})
    return results


def chunk_text(text: str, max_tokens: int = 6000, overlap: int = 200) -> list[str]:
    """Split text into chunks respecting paragraph boundaries."""
    max_chars = max_tokens * 4  # ~4 chars per token for Vietnamese
    overlap_chars = overlap * 4

    if len(text) <= max_chars:
        return [text]

    paragraphs = text.split('\n\n')
    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 > max_chars:
            if current:
                chunks.append(current.strip())
            # Start new chunk with overlap from end of previous
            if chunks and overlap_chars > 0:
                current = chunks[-1][-overlap_chars:] + "\n\n" + para
            else:
                current = para
            # Handle single paragraph longer than max
            if len(current) > max_chars:
                sentences = re.split(r'(?<=[.!?])\s+', current)
                current = ""
                for sent in sentences:
                    if len(current) + len(sent) > max_chars:
                        if current:
                            chunks.append(current.strip())
                        current = sent
                    else:
                        current += " " + sent if current else sent
        else:
            current += "\n\n" + para if current else para

    if current.strip():
        chunks.append(current.strip())

    return [c for c in chunks if len(c.strip()) > 50]  # Skip tiny fragments


def estimate_tokens(text: str) -> int:
    return len(text) // 4  # Rough estimate: ~4 chars per token


def write_json(data: Any, path: str) -> None:
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_json(path: str) -> Any:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_file(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def create_zip(source_dir: str, output_path: str) -> str:
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        base = Path(source_dir)
        for file_path in base.rglob('*'):
            if file_path.is_file() and file_path.name != 'package.zip':
                if file_path.name.startswith('.') or 'checkpoint' in file_path.name:
                    continue
                arcname = file_path.relative_to(base)
                zf.write(file_path, arcname)
    return output_path
