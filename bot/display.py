from enum import Enum, auto
from typing import Dict, Optional

import telegram

GM_SYMBOL = '✧'

HELP_ZH_HANS = '''<b>基本指令</b>

<code>/name [角色名]</code> - 设置角色名
<code>.[...发言...]</code> - 以 <code>.</code>为开头的消息视作角色发言
<code>.[...某些内容...] .me [...某些内容...]</code> - 角色名占位符，描述角色动作和行为
<code>.del</code> - 回复自己的一条消息，删掉这条
<code>.edit ...</code> - 回复自己的一条消息，修改这条
<code>.r XdY [...描述...]</code> - 投掷骰子，X或Y都可以省略
<code>.coc [技能值]</code> - CoC 第七版骰子
<code>/face [面数]</code>- 设置默认骰子面数（默认20面）

/save - 停止记录
/start - 重新开始记录

还有很多功能如战斗轮指示器、临时角色切换等，<a href="http://wiki.aleadea.com/index.php/Telegram_TRPG_%E6%9C%BA%E5%99%A8%E4%BA%BA%E6%8C%87%E4%BB%A4%E6%96%87%E6%A1%A3">请点击这里查看详细指令介绍</a>
请前往 https://log.paotuan.space/ 查看你的日志
为了输入方便，所有命令开头的 <code>.</code> 都可以用 <code>。</code> 代替
'''

HELP_ZH_HANT = '''<b>基本指令</b>

<code>/name [角色名]</code> - 設置角色名
<code>.[...發言...]</code> - 以 <code>.</code>爲開頭的消息視作角色發言
<code>.[...某些內容...] .me [...某些內容...]</code> - 角色名佔位符，描述角色動作和行爲
<code>.del</code> - 回覆自己的一條消息，刪掉這條
<code>.edit ...</code> - 回覆自己的一條消息，修改這條
<code>.r XdY [...描述...]</code> - 投擲骰子，X或Y都可以省略
<code>.coc [技能值]</code> - CoC 第七版骰子
<code>/face [面數]</code>- 設置默認骰子面數（默認20面）

/save - 停止記錄
/start - 重新開始記錄

還有很多功能如戰鬥輪指示器、臨時角色切換等，<a href="http://wiki.aleadea.com/index.php/Telegram_TRPG_%E6%9C%BA%E5%99%A8%E4%BA%BA%E6%8C%87%E4%BB%A4%E6%96%87%E6%A1%A3">請點擊這裏查看詳細指令介紹</a>
請前往 https://log.paotuan.space/ 查看你的日誌
爲了輸入方便，所有命令開頭的 <code>.</code> 都可以用 <code>。</code> 代替
'''

START_ZH_HANS = '''
我是用来帮助在 Telegram 中<a href="http://wiki.aleadea.com/index.php/TRPG">玩桌面角色扮演游戏</a>而诞生的

要开始使用，请给我管理员权限，<a href="http://wiki.aleadea.com/index.php/Telegram_TRPG_%E6%9C%BA%E5%99%A8%E4%BA%BA">详细使用步骤请参阅这里</a>。

所有以「.」或「。」开头的消息将被我处理。<b>注意我会记录这些消息在数据库内！</b>

开始前需要输入 <code>/name 你的角色名</code>，<a href="http://wiki.aleadea.com/index.php/Telegram_TRPG_%E6%9C%BA%E5%99%A8%E4%BA%BA%E6%8C%87%E4%BB%A4%E6%96%87%E6%A1%A3">这里是所有命令说明</a>

<a href="https://logs.paotuan.space"> 在这里可以查看记录下的日志</a>

祝冒险愉快！
'''


START_ZH_HANT = '''
我是用來幫助在 Telegram 中<a href="http://wiki.aleadea.com/index.php/TRPG">玩桌面角色扮演遊戲</a>而誕生的

要開始使用，請給我管理員權限，<a href="http://wiki.aleadea.com/index.php/Telegram_TRPG_%E6%9C%BA%E5%99%A8%E4%BA%BA">詳細使用步驟請參閱這裏</a>。

所有以「.」或「。」開頭的消息將被我處理。<b>注意我會記錄這些消息在數據庫內！</b>

開始前需要輸入 <code>/name 你的角色名</code>，<a href="http://wiki.aleadea.com/index.php/Telegram_TRPG_%E6%9C%BA%E5%99%A8%E4%BA%BA%E6%8C%87%E4%BB%A4%E6%96%87%E6%A1%A3">這裏是所有命令說明</a>

<a href="https://logs.paotuan.space"> 在這裏可以查看記錄下的日誌</a>

祝冒險愉快！
'''


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
    REPLY_TO_NON_PLAYER_IN_VARIABLE_ASSIGNMENT = auto()
    ALREADY_SAVED = auto()
    VARIABLE_ASSIGNED = auto()
    VARIABLE_ASSIGNED_EMPTY = auto()
    VARIABLE_UPDATED = auto()
    VARIABLE_ASSIGN_USAGE = auto()
    VARIABLE_NOT_CHANGE = auto()
    VARIABLE_CLEARED = auto()
    VARIABLE_LIST_TITLE = auto()
    VARIABLE_LIST_BUTTON = auto()
    VARIABLE_LIST_EMPTY = auto()
    ZERO_DIVISION = auto()
    ROLL_SYNTAX_ERROR = auto()


zh_hans: Dict[Text, str] = {
    Text.ZERO_DIVISION: '零不能作除数',
    Text.ROLL_SYNTAX_ERROR: '投骰子时出现语法错误',
    Text.VARIABLE_CLEARED: '{character} 的指代已清空',
    Text.VARIABLE_LIST_TITLE: '{character} 的指代',
    Text.VARIABLE_LIST_EMPTY: '没有建立任何指代',
    Text.VARIABLE_LIST_BUTTON: '查看我的指代',
    Text.VARIABLE_UPDATED: '{character} 的 <code>{variable}</code> 已变动: '
                           '<code>{old_value}</code> → <code>{value}</code>',
    Text.REPLY_TO_NON_PLAYER_IN_VARIABLE_ASSIGNMENT: 'GM 可以通过 @ 或回复别的玩家 <code>.set 指代名 所指内容</code> '
                                                     '来为别的玩家建立指代。但是你所回复的消息不和一个玩家所关联。',
    Text.VARIABLE_ASSIGN_USAGE: '建立指代： <code>.set HP 42</code>\n'
                                '指代名可以用中文、英文数字和下划线，1-32个字符\n'
                                '可以分多行一次建立多个指代',
    Text.VARIABLE_ASSIGNED: '{character} 的 <code>{variable}</code> 已设为 <code>{value}</code>',
    Text.VARIABLE_ASSIGNED_EMPTY: '{character} 的 <code>{variable}</code> 已添加',
    Text.VARIABLE_NOT_CHANGE: '{character} 的 <code>{variable}</code> 没有变动，仍然是 <code>{value}</code>',
    Text.START_RECORDING: '已重新开始记录，输入 /save 告一段落',
    Text.SAVE: '告一段落，在 /start 前我不会再记录',
    Text.ALREADY_STARTED: '已经正在记录了',
    Text.ALREADY_SAVED: '已经停止记录了',
    Text.REPLACE_USAGE: '请用<code>/</code>分开需要替换的两部分，如 <code>苹果/香蕉</code>',
    Text.NOT_SET_NAME: '请先使用 <code>/name [你的角色名]</code> 设置角色名',
    Text.PASSWORD_SUCCESS: '密码已设置',
    Text.PASSWORD_USAGE: '输入 <code>/password [你的密码]</code> 设置密码。密码中不能有空格。',
    Text.DELETE_FAIL: '删除消息失败，请检查一下 bot 的权限设置',
    Text.HELP_TEXT: HELP_ZH_HANS,
    Text.START_TEXT: START_ZH_HANS,
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


zh_hant: Dict[Text, str] = {
    Text.ZERO_DIVISION: '零不能作除數',
    Text.ROLL_SYNTAX_ERROR: '投骰子時出現語法錯誤',
    Text.VARIABLE_CLEARED: '{character} 的指代已清空',
    Text.VARIABLE_LIST_TITLE: '{character} 的指代',
    Text.VARIABLE_LIST_EMPTY: '沒有建立任何指代',
    Text.VARIABLE_LIST_BUTTON: '查看我的指代',
    Text.VARIABLE_UPDATED: '{character} 的 <code>{variable}</code> 已變動: '
                           '<code>{old_value}</code> → <code>{value}</code>',
    Text.REPLY_TO_NON_PLAYER_IN_VARIABLE_ASSIGNMENT: 'GM 可以通過 @ 或回覆別的玩家 <code>.set 指代名 所指內容</code> '
                                                     '來爲別的玩家建立指代。但是你所回覆的消息不和一個玩家所關聯。',
    Text.VARIABLE_ASSIGN_USAGE: '建立指代： <code>.set HP 42</code>\n'
                                '指代名可以用中文、英文數字和下劃線，1-32個字符\n'
                                '可以分多行一次建立多個指代',
    Text.VARIABLE_ASSIGNED: '{character} 的 <code>{variable}</code> 已設爲 <code>{value}</code>',
    Text.VARIABLE_ASSIGNED_EMPTY: '{character} 的 <code>{variable}</code> 已添加',
    Text.VARIABLE_NOT_CHANGE: '{character} 的 <code>{variable}</code> 沒有變動，仍然是 <code>{value}</code>',
    Text.START_RECORDING: '已重新開始記錄，輸入 /save 告一段落',
    Text.SAVE: '告一段落，在 /start 前我不會再記錄',
    Text.ALREADY_STARTED: '已經正在記錄了',
    Text.ALREADY_SAVED: '已經停止記錄了',
    Text.REPLACE_USAGE: '請用<code>/</code>分開需要替換的兩部分，如 <code>蘋果/香蕉</code>',
    Text.NOT_SET_NAME: '請先使用 <code>/name [你的角色名]</code> 設置角色名',
    Text.PASSWORD_SUCCESS: '密碼已設置',
    Text.PASSWORD_USAGE: '輸入 <code>/password [你的密碼]</code> 設置密碼。密碼中不能有空格。',
    Text.DELETE_FAIL: '刪除消息失敗，請檢查一下 bot 的權限設置',
    Text.HELP_TEXT: HELP_ZH_HANT,
    Text.START_TEXT: HELP_ZH_HANS,
    Text.ERROR: '錯誤',
    Text.UNKNOWN_COMMAND: '未知指令',
    Text.RECORD_NOT_FOUND: '沒有找到記錄，請確認所回覆的消息',
    Text.NEED_REPLY: '你需要先回復一條 bot 發出的信息',
    Text.HAVE_NOT_PERMISSION: '你沒有對這條信息操作的權限',
    Text.NEED_REPLY_PLAYER_RECORD: '需要回復一條玩家發出的消息',
    Text.NOT_RECORDING: '未記錄',
    Text.EMPTY_NAME: '名字不能爲空',
    Text.NOT_GM: '只有 GM 才能這樣操作',
    Text.AS_SYNTAX_ERROR: '''.as 的用法是 .as [名字]; [內容]。
如果之前用過 .as 的話可以省略名字的部分，直接寫 .as [內容]。
但你之前並沒有用過 .as''',
    Text.EMPTY_MESSAGE: '不能有空消息',
    Text.NAME_SYNTAX_ERROR: '請在 <code>/name</code> 後寫下你的角色名',
    Text.NAME_SUCCESS: '<b>玩家</b> {player} 已設爲 {character}',
    Text.NAME_SUCCESS_GM: '<b>主持人</b> {player} 已設爲 {character}',
    Text.SET_DEFAULT_FACE_SYNTAX: '需要（且僅需要）指定骰子的默認面數，目前爲 <b>{face}</b>',
    Text.FACE_ONLY_ALLOW_NUMBER: '面數只能是數字',
    Text.COC_NEED_SKILL_VALUE: '格式錯誤。需要寫技能值。',
    Text.COC_BONUS_DIE: '獎勵骰',
    Text.COC_CRITICAL: '大成功',
    Text.COC_EXTREME_SUCCESS: '極難成功',
    Text.COC_FAIL: '失敗',
    Text.COC_FUMBLE: '大失敗',
    Text.COC_HARD_SUCCESS: '困難成功',
    Text.COC_PENALTY_DIE: '懲罰骰',
    Text.COC_REGULAR_SUCCESS: '成功',
    Text.LOOP_SYNTAX_ERROR: '格式錯誤。需要 <code>.loop [個數，最多兩位數] [可選的描述]</code>',
    Text.LOOP_ZERO_DICE: '錯誤，不能 roll 0 個骰子',
    Text.GM_LOOKUP: 'GM 查看',
    Text.ROLL_HIDE_DICE: '投了一個隱形骰子',
    Text.ONLY_GM_CAN_LOOKUP: '暗骰只有 GM 才能查看',
    Text.HIDE_ROLL_NOT_FOUND: '找不到這條暗骰記錄，暗骰記錄會定期清理掉',
    Text.ROUND_REMOVE: '刪除',
    Text.ROUND_FINISH: '結束',
    Text.ALREADY_FIRST_TURN: '已經是第一回合了',
    Text.AT_LEAST_ONE_ACTOR: '至少要有一位角色在回合中',
    Text.ROUND_ALREADY_FINISHED: '回合輪已結束',
    Text.GAME_NOT_IN_ROUND: '現在遊戲沒在回合狀態之中',
    Text.HIDED_ROUND_LIST: '隱藏列表',
    Text.ROUND_INDICATOR: '回合指示器',
    Text.ROUND_INDICATOR_INIT: '沒有人加入回合，使用 <code>.init [值]</code> 來加入回合\n\n可以用 /hide 將回合列表轉爲隱藏式',
    Text.ROUND_COUNTER: '第 {round_number} 輪',
    Text.CURRENT: '當前',
    Text.NOT_GROUP: '必須在羣聊中使用此命令',
    Text.INIT_USAGE: '用法： <code>.init [數字]</code> 或 <code>.init [角色名] = [數字]</code>',
    Text.INIT_WITHOUT_ROUND: '請先用 /round 指令開啓回合輪',
}


language_map: Dict[str, Dict[Text, str]] = {
    'zh-hans': zh_hans,
    'zh-hant': zh_hant,
    'zh-Hans': zh_hans,
    'zh-Hant': zh_hant,
    'zh-CN': zh_hans,
    'zh-TW': zh_hant,
    'zh-HK': zh_hant,
    'zh-cn': zh_hans,
    'zh-tw': zh_hant,
    'zh-hk': zh_hant,
}


def get(x: Text, language_code='zh-hans') -> str:
    return language_map.get(language_code, zh_hans)[x]


def get_by_user(x: Text, user: Optional[telegram.User] = None):
    if not isinstance(user, telegram.User):
        return get(x)
    return get(x, user.language_code)
