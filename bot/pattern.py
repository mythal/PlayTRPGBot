import re
from typing import Optional, Tuple

# name = 42
INITIATIVE_REGEX = re.compile(r'^(.+)=\s*(\d{1,4})$')

# ..(space)..42..{space}..
LOOP_ROLL_REGEX = re.compile(r'^\s*(\d{1,2})\s*')

# .me
ME_REGEX = re.compile(r'^[.。]me\b|\s[.。]me\s?')

# @some_user_name
USERNAME_REGEX = re.compile(r'@([a-zA-Z0-9_]{5,})')

# ..(space)..[name];..(space)..
AS_REGEX = re.compile(r'^\s*([^;]+)[;；]\s*')

EDIT_COMMANDS_REGEX = re.compile(r'^[.。](del|edit|lift|s)\b')


def split(pattern, text) -> Optional[Tuple[str, int]]:
    result = re.match(pattern, text)
    if result is None:
        return None
    else:
        command = result.group(1)
        return command, result.end()
