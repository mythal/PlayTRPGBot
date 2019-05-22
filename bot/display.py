from enum import Enum, auto
from typing import Dict, Any, Union

GM_SYMBOL = '✧'

_help_file = open('./help.md')
_start_file = open('./start.md')
HELP_TEXT: str = _help_file.read()
START_TEXT: str = _start_file.read()
_help_file.close()
_start_file.close()


class Text(Enum):
    HELP_TEXT = auto()
    START_TEXT = auto()
    ERROR = auto()
    UNKNOWN_COMMAND = auto()
    RECORD_NOT_FOUND = auto()
    NEED_REPLY = auto()
    DELETE_FAIL = auto()
    NOT_RECORDING = auto()
    EMPTY_NAME = auto()
    NOT_GM = auto()
    AS_SYNTAX_ERROR = auto()
    EMPTY_MESSAGE = auto()
    NAME_SYNTAX_ERROR = auto()
    NAME_SUCCESS = auto()
    NAME_SUCCESS_GM = auto()
    SET_DEFAULT_FACE_SYNTAX = auto()
    FACE_ONLY_ALLOW_NUMBER = auto()
    COC_NEED_SKILL_VALUE = auto()
    COC_BONUS_DIE = auto()
    COC_PENALTY_DIE = auto()
    COC_REGULAR_SUCCESS = auto()
    COC_HARD_SUCCESS = auto()
    COC_EXTREME_SUCCESS = auto()
    COC_FAIL = auto()
    COC_FUMBLE = auto()
    COC_CRITICAL = auto()
    LOOP_SYNTAX_ERROR = auto()
    LOOP_ZERO_DICE = auto()
    GM_LOOKUP = auto()
    ONLY_GM_CAN_LOOKUP = auto()
    ROLL_HIDE_DICE = auto()
    HIDE_ROLL_NOT_FOUND = auto()
    ROUND_REMOVE = auto()
    ROUND_FINISH = auto()
    ALREADY_FIRST_TURN = auto()
    AT_LEAST_ONE_ACTOR = auto()
    ROUND_ALREADY_FINISHED = auto()
    GAME_NOT_IN_ROUND = auto()
    HIDED_ROUND_LIST = auto()
    ROUND_INDICATOR = auto()
    ROUND_INDICATOR_INIT = auto()
    ROUND_COUNTER = auto()
    CURRENT = auto()
    NOT_GROUP = auto()
    INIT_USAGE = auto()
    INIT_WITHOUT_ROUND = auto()
    HAVE_NOT_PERMISSION = auto()
    NEED_REPLY_PLAYER_RECORD = auto()
    PASSWORD_USAGE = auto()
    PASSWORD_SUCCESS = auto()
    NOT_SET_NAME = auto()
    REPLACE_USAGE = auto()
    START_RECORDING = auto()
    ALREADY_STARTED = auto()
    SAVE = auto()
    PLAYER_NOT_FOUND = auto()
    ALREADY_SAVED = auto()
    VARIABLE_ASSIGNED = auto()
    VARIABLE_ASSIGNED_EMPTY = auto()
    VARIABLE_UPDATED = auto()
    VARIABLE_ASSIGN_USAGE = auto()
    VARIABLE_LIST_TITLE = auto()
    VARIABLE_NOT_CHANGE = auto()


text_table: Dict[Text, str] = {
    Text.VARIABLE_LIST_TITLE: '{character} 的变量',
    Text.VARIABLE_UPDATED: '{character} 的 <code>{variable}</code> 已变动\n'
                           '<code>{old_value}</code> → <code>{value}</code>',
    Text.PLAYER_NOT_FOUND: '没有找到玩家，请尝试重新执行一下 <code>/name</code>',
    Text.VARIABLE_ASSIGN_USAGE: '设置变量语法： <code>.set 变量名 变 量 值，可 以 有 空 格</code>\n'
                                '变量名可以用中文、英文数字和下划线，1-32个字符',
    Text.VARIABLE_ASSIGNED: '{character} 的 <code>{variable}</code> 已设为 <code>{value}</code>',
    Text.VARIABLE_ASSIGNED_EMPTY: '{character} 的 <code>{variable}</code> 已添加',
    Text.VARIABLE_NOT_CHANGE: '{character} 的 <code>{variable}</code> 没有变动',
    Text.START_RECORDING: '已重新开始记录，输入 /save 告一段落',
    Text.SAVE: '告一段落，在 /start 前我不会再记录',
    Text.ALREADY_STARTED: '已经正在记录了',
    Text.ALREADY_SAVED: '已经停止记录了',
    Text.REPLACE_USAGE: '请用<code>/</code>分开需要替换的两部分，如 <code>苹果/香蕉</code>',
    Text.NOT_SET_NAME: '请先使用 <code>/name [你的角色名]</code> 设置角色名',
    Text.PASSWORD_SUCCESS: '密码已设置',
    Text.PASSWORD_USAGE: '输入 <code>/password [你的密码]</code> 设置密码。密码中不能有空格。',
    Text.DELETE_FAIL: '删除消息失败，请检查一下 bot 的权限设置',
    Text.HELP_TEXT: HELP_TEXT,
    Text.START_TEXT: START_TEXT,
    Text.ERROR: '错误',
    Text.UNKNOWN_COMMAND: '未知指令',
    Text.RECORD_NOT_FOUND: '没有找到记录，请确认所回复的消息',
    Text.NEED_REPLY: '你需要先回复一条 bot 发出的信息',
    Text.HAVE_NOT_PERMISSION: '你没有对这条信息操作的权限',
    Text.NEED_REPLY_PLAYER_RECORD: '需要回复一条玩家发出的消息',
    Text.NOT_RECORDING: '未记录',
    Text.EMPTY_NAME: '名字不能为空',
    Text.NOT_GM: '只有 GM 才能这样操作',
    Text.AS_SYNTAX_ERROR: '''.as 的用法是 .as [名字]; [内容]。
如果之前用过 .as 的话可以省略名字的部分，直接写 .as [内容]。
但你之前并没有用过 .as''',
    Text.EMPTY_MESSAGE: '不能有空消息',
    Text.NAME_SYNTAX_ERROR: '请在 <code>/name</code> 后写下你的角色名',
    Text.NAME_SUCCESS: '<b>玩家</b> {player} 已设为 {character}',
    Text.NAME_SUCCESS_GM: '<b>主持人</b> {player} 已设为 {character}',
    Text.SET_DEFAULT_FACE_SYNTAX: '需要（且仅需要）指定骰子的默认面数，目前为 <b>{face}</b>',
    Text.FACE_ONLY_ALLOW_NUMBER: '面数只能是数字',
    Text.COC_NEED_SKILL_VALUE: '格式错误。需要写技能值。',
    Text.COC_BONUS_DIE: '奖励骰',
    Text.COC_CRITICAL: '大成功',
    Text.COC_EXTREME_SUCCESS: '极难成功',
    Text.COC_FAIL: '失败',
    Text.COC_FUMBLE: '大失败',
    Text.COC_HARD_SUCCESS: '困难成功',
    Text.COC_PENALTY_DIE: '惩罚骰',
    Text.COC_REGULAR_SUCCESS: '成功',
    Text.LOOP_SYNTAX_ERROR: '格式错误。需要 <code>.loop [个数，最多两位数] [可选的描述]</code>',
    Text.LOOP_ZERO_DICE: '错误，不能 roll 0 个骰子',
    Text.GM_LOOKUP: 'GM 查看',
    Text.ROLL_HIDE_DICE: '投了一个隐形骰子',
    Text.ONLY_GM_CAN_LOOKUP: '暗骰只有 GM 才能查看',
    Text.HIDE_ROLL_NOT_FOUND: '找不到这条暗骰记录，暗骰记录会定期清理掉',
    Text.ROUND_REMOVE: '删除',
    Text.ROUND_FINISH: '结束',
    Text.ALREADY_FIRST_TURN: '已经是第一回合了',
    Text.AT_LEAST_ONE_ACTOR: '至少要有一位角色在回合中',
    Text.ROUND_ALREADY_FINISHED: '回合轮已结束',
    Text.GAME_NOT_IN_ROUND: '现在游戏没在回合状态之中',
    Text.HIDED_ROUND_LIST: '隐藏列表',
    Text.ROUND_INDICATOR: '回合指示器',
    Text.ROUND_INDICATOR_INIT: '没有人加入回合，使用 <code>.init [值]</code> 来加入回合\n\n可以用 /hide 将回合列表转为隐藏式',
    Text.ROUND_COUNTER: '第 {round_number} 轮',
    Text.CURRENT: '当前',
    Text.NOT_GROUP: '必须在群聊中使用此命令',
    Text.INIT_USAGE: '用法： <code>.init [数字]</code> 或 <code>.init [角色名] = [数字]</code>',
    Text.INIT_WITHOUT_ROUND: '请先用 /round 指令开启回合轮',
}


def get(x: Text) -> str:
    return text_table[x]
