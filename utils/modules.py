import re
from typing import Optional


def extract_module_code_and_name(
    module_str: str,
) -> tuple[Optional[str], Optional[str]]:
    if not module_str or not module_str.strip():
        return None, None

    module_str = module_str.strip()

    pattern = r"^([A-Z]+\s?\d+)\s+(.+)$"
    match = re.match(pattern, module_str)

    if match:
        code = match.group(1).strip()
        name = match.group(2).strip()
        return code, name

    parts = module_str.split(maxsplit=1)
    if len(parts) == 2:
        return parts[0], parts[1]
    elif len(parts) == 1:
        return parts[0], None

    return None, None
