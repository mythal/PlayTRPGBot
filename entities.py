from __future__ import annotations

import re
from typing import List, Optional


class Entity:
    kind = 'none'
    value = None

    def object(self) -> dict:
        obj = self.__dict__
        obj['kind'] = self.kind
        return obj

    def html(self):
        return ''

    @staticmethod
    def from_object(obj: dict) -> Entity:
        raise NotImplementedError()

    def __repr__(self):
        return '<{}| {}>'.format(self.kind, self.value)


class Entities:
    list: List[Entity]

    def __init__(self, li=None):
        self.list = li or []

    def to_object(self) -> List[dict]:
        return make_entities_object(self.list)

    @staticmethod
    def from_html(html: str) -> Entities:
        new = Entities()
        new.list = convert_to_entities(html)
        return new

    def to_html(self) -> str:
        return entities_to_html(self.list)


class Span(Entity):
    kind = 'span'

    def __init__(self, text):
        self.value = text

    def html(self):
        return self.value

    @staticmethod
    def from_object(obj: dict) -> Span:
        return Span(obj['value'])


class Character(Entity):
    kind = 'character'

    def __init__(self, character: str, player_id: int, full_name: str):
        self.value = character
        self.player_id = player_id
        self.full_name = full_name

    def html(self):
        return '<b>{}</b>'.format(self.value)

    @staticmethod
    def from_object(obj: dict) -> Character:
        return Character(obj['value'], obj['player_id'], obj['full_name'])


class Me(Character):
    kind = 'me'

    @staticmethod
    def from_object(obj: dict) -> Me:
        return Me(obj['value'], obj['player_id'], obj['full_name'])


class Bold(Entity):
    kind = 'bold'

    def __init__(self, text):
        self.value = text

    def html(self):
        return '<b>{}</b>'.format(self.value)

    @staticmethod
    def from_object(obj: dict) -> Bold:
        return Bold(obj['value'])


class Code(Entity):
    kind = 'code'

    def __init__(self, text):
        self.value = text

    def html(self):
        return '<code>{}</code>'.format(self.value)

    @staticmethod
    def from_object(obj: dict) -> Code:
        return Code(obj['value'])


class RollResult(Entity):
    kind = 'roll'

    def __init__(self, text, result=None):
        self.value = text
        self.result = result

    def html(self):
        return ' <code>{}</code> '.format(self.value)

    @staticmethod
    def from_object(obj: dict) -> RollResult:
        return RollResult(obj['value'], obj['result'])


class LoopResult(Entity):
    kind = 'loop-roll'

    def __init__(self, rolled: List[int]):
        self.rolled = rolled

    def html(self):
        counter_6 = self.rolled.count(6)
        counter_all = len(self.rolled)
        rolled_text = ', '.join(map(str, self.rolled))
        return ' <code>({}/{}) [{}]</code> '.format(counter_6, counter_all, rolled_text)

    @staticmethod
    def from_object(obj: dict) -> LoopResult:
        return LoopResult(obj['rolled'])


class CocResult(Entity):
    kind = 'coc-roll'

    def __init__(self, rolled: int, level: str,
                 modifier_name: Optional[str], rolled_list: List[int]):
        self.rolled = rolled
        self.level = level
        self.modifier_name = modifier_name
        self.rolled_list = rolled_list

        self.value = level

    def html(self):
        result = '<code>{rolled}</code> {level}'.format(
            rolled=self.rolled, level=self.level,
        )
        if self.modifier_name:
            result += '\n\n{modifier_name}: <code>{rolled_list}</code>'.format(
                modifier_name=self.modifier_name,
                rolled_list=', '.join(map(str, self.rolled_list)),
            )
        return result

    @staticmethod
    def from_object(obj: dict) -> CocResult:
        return CocResult(obj['rolled'], obj['level'], obj['modifier_name'], obj['rolled_list'])


CODE_REGEX = re.compile(r'<(code)>(.+?)</code>')
BOLD_REGEX = re.compile(r'<(b)>(.+?)</b>')


def convert_to_entities(content: str) -> List[Entity]:
    matches = list(CODE_REGEX.finditer(content))
    matches.extend(BOLD_REGEX.finditer(content))
    matches.sort(key=lambda m: m.start())
    entities = []
    last_index = 0
    for match in matches:
        tag = match.group(1)
        text = match.group(2)
        start = match.start()
        if start < last_index:
            continue
        segment = content[last_index:start]
        if segment:
            entities.append(Span(segment))
        last_index = match.end()
        if tag == 'code':
            entities.append(Code(text))
        elif tag == 'b':
            entities.append(Bold(text))
    if last_index < len(content) - 1:
        entities.append(Span(content[last_index:]))
    return entities


def entities_to_html(entities: List[Entity]) -> str:
    html = ''.join(map(lambda e: e.html(), entities))
    return html.strip()


def make_entities_object(entities: List[Entity]):
    return list([entity.object() for entity in entities])


def object_to_entity(obj: dict) -> Optional[Entity]:
    kind = obj.get('kind', '')
    for E in (Span, Character, Me, Bold, Code, RollResult, LoopResult, CocResult):
        if E.kind == kind:
            return E.from_object(obj)
    return None

