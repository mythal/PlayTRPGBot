import re
from typing import Optional, Tuple

# name = 42
INITIATIVE_REGEX = re.compile(r'^(.+)=\s*(\d{1,4})$')

# ..(space)..42..{space}..
LOOP_ROLL_REGEX = re.compile(r'^\s*(\d{1,2})\s*')

# .me
ME_REGEX = re.compile(r'[.。]me(?![a-zA-Z0-9_\-])')

# @some_user_name
USERNAME_REGEX = re.compile(r'@([a-zA-Z0-9_]{5,})')

# ..(space)..[name];..(space)..
AS_REGEX = re.compile(r'^[.。【[]as\s*([^;；]+)[;；]\s*')

VARIABLE_REGEX = re.compile(r'[$¥]([\w_0-9]{1,32})')

VARIABLE_NAME_REGEX = re.compile(r'[$¥]?([\w_0-9]{1,32})')

VARIABLE_MODIFY_REGEX = re.compile(r'^\s*[$¥]?([\w_0-9]{1,32})\s*([+\-])\s*')

VARIABLE_IGNORE_HEAD = re.compile(r'^\s*=\s*')


def split(patterns, text: str) -> Optional[Tuple[str, int]]:
    result = re.match(patterns, text.lower())
    if result is None:
        return None
    else:
        command = result.group(1)
        return command, result.end()
