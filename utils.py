from datetime import datetime
from zoneinfo import ZoneInfo

MAX_EMBED_DESCRIPTION = 4096
CODE_BLOCK_OVERHEAD = 8
CHUNK_LENGTH = MAX_EMBED_DESCRIPTION - CODE_BLOCK_OVERHEAD

def split_into_chunks(text: str, max_length: int = CHUNK_LENGTH) -> list[str]:
    lines = text.splitlines(keepends=True)
    chunks = []
    current_chunk = ""
    for line in lines:
        if len(current_chunk) + len(line) > max_length:
            chunks.append(current_chunk)
            current_chunk = line
        else:
            current_chunk += line
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

def clean_name(line: str) -> str:
    lower_line = line.lower()
    if "abyss" in lower_line:
        return "abyss"
    if "mob" in lower_line:
        return "mob"
    if "killa" in lower_line:
        return "Killa"
    if "nebu" in lower_line:
        return "xNebu"
    if "tinta china" in lower_line:
        return "ャンクス"
    if "rjdi0" in lower_line or "ridio" in lower_line:
        return "rjdio"
    if "dato" in lower_line:
        return "d4to"
    if "redf 4 wkez" in lower_line or "redf 4wkez" in lower_line:
        return "redfawkes"
    return line