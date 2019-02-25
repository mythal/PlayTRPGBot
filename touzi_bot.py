import logging
import os
import re
import secrets
from secrets import choice
from typing import List
from uuid import uuid4

import telegram
from dotenv import load_dotenv
from faker import Faker
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent, ParseMode
from telegram.ext import Updater, CommandHandler, InlineQueryHandler

import dice

MAX_FACE = 1000
MAX_NUM = 200

load_dotenv()
TOKEN = os.environ['TOUZI_BOT_TOKEN']

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)


class UnsupportedDice(Exception):
    pass


class Dice:
    DEFAULT_NUM = 1

    def __init__(self, face_num: int):
        self.face = face_num

    def roll(self) -> int:
        return secrets.randbelow(self.face) + 1

    def roll_n(self, dice_num) -> [int]:
        return [self.roll() for _ in range(dice_num)]

    def display(self, roll_result: [int]):
        result = ", ".join(["{}".format(r) for r in roll_result])
        num = len(roll_result)
        if num == 1:
            return "`1d{}` 🎲 `{}`".format(self.face, result)
        else:
            return "`{}d{}` 🎲 `{}`\nsum: `{}` max: `{}` min: `{}`".format(
                num, self.face, result, sum(roll_result), max(roll_result), min(roll_result))


def db_and_build(stats: dict):
    a = stats['str'] + stats['size']
    if a < 65:
        db, build = '-2', -2
    elif a < 85:
        db, build = '-1', -1
    elif a < 125:
        db, build = '0', 0
    elif a < 165:
        db, build = '+1d4', 1
    elif a < 205:
        db, build = '+1d6', 2
    elif a < 285:
        db, build = '+2d6', 3
    elif a < 365:
        db, build = '+3d6', 4
    elif a < 445:
        db, build = '+4d6', 5
    else:
        db, build = '+5d6', 6
    stats['db'] = db
    stats['build'] = build


def random_age() -> int:
    age = 100
    for _ in range(5):
        age = min(secrets.randbelow(65) + 15, age)
    return age


def coc7stats_text(age=None):
    warning = ""
    is_random_age = age is None
    if age is None:
        age = random_age()

    d6 = Dice(6)
    d10 = Dice(10)
    d100 = Dice(100)

    stats = {
        "age": age,
        "str": sum(d6.roll_n(3)) * 5,
        "con": sum(d6.roll_n(3)) * 5,
        "dex": sum(d6.roll_n(3)) * 5,
        "pow_": sum(d6.roll_n(3)) * 5,
        "app": sum(d6.roll_n(3)) * 5,
        "luck": sum(d6.roll_n(3)) * 5,
        "luck2": sum(d6.roll_n(3)) * 5,
        "size": sum(d6.roll_n(2), 6) * 5,
        "int": sum(d6.roll_n(2), 6) * 5,
        "edu": sum(d6.roll_n(2), 6) * 5,
        "mov": 8,
    }
    if is_random_age:
        stats['random_age_text'] = '你没有指定年龄，就当你是{}岁好了\n'.format(age)
    else:
        stats['random_age_text'] = ''

    if stats['dex'] < stats['size'] and stats['str'] < stats['size']:
        stats['mov'] = 7
    elif stats['dex'] > stats['size'] and stats['str'] > stats['size']:
        stats['mov'] = 9

    def edu_enhance(time: int, edu: int):
        track = []
        for _ in range(time):
            if d100.roll() > edu:
                delta = d10.roll()
                edu += delta
                track.append(delta)
        return min(99, edu)

    if age < 15:
        warning += "小于十五岁的调查员需要咨询KP调整属性值"
    elif age < 20:
        warning += "请将力量和体型合计减 5 点。\n\n幸运已投掷两次取了大值（可放弃） {} {}" \
            .format(stats['luck'], stats['luck2'])
        stats['luck'] = max(stats['luck'], stats['luck2'])
    elif age < 40:
        stats['edu'] = edu_enhance(1, stats['edu'])
    elif age < 50:
        warning += "请将力量、敏捷和体质合计减 5 点。"
        stats['app'] -= 5
        stats['mov'] -= 1
        stats['edu'] = edu_enhance(2, stats['edu'])
    elif age < 60:
        warning += "请将力量、敏捷和体质合计减 10 点。"
        stats['app'] -= 10
        stats['mov'] -= 2
        stats['edu'] = edu_enhance(3, stats['edu'])
    elif age < 70:
        warning += "请将力量、敏捷和体质合计减 20 点。"
        stats['app'] -= 15
        stats['mov'] -= 3
        stats['edu'] = edu_enhance(4, stats['edu'])
    elif age < 80:
        warning += "请将力量、敏捷和体质合计减 40 点。"
        stats['app'] -= 20
        stats['mov'] -= 4
        stats['edu'] = edu_enhance(4, stats['edu'])
    elif age <= 90:
        warning += "请将力量、敏捷和体质合计减 80 点。"
        stats['app'] -= 25
        stats['mov'] -= 5
        stats['edu'] = edu_enhance(4, stats['edu'])
    else:
        warning += "大于九十岁的调查员请询问KP"
    db_and_build(stats)
    stats['hp'] = (stats['size'] + stats['con']) // 10

    stats['mp'] = stats['pow_'] // 5

    stats_text = '''
```
力量  STR: {str:2}  
体质  CON: {con:2}
体形  SIZ: {size:2}  
敏捷  DEX: {dex:2}
外表  APP: {app:2}
教育  EDU: {edu:2}
智力  INT: {int:2}
意志  POW: {pow_:2}
幸运 Luck: {luck:2}
体力  HP: {hp:2}
理智 SAN: {pow_:2}
魔法  MP: {mp:2}
移动力 MOV: {mov:2}
体格 Build: {build:2}
伤害加值 DB: {db:2}
```
{random_age_text}
已根据年龄（{age}）调整了教育、移动力以及幸运。
{0}'''.format(warning, **stats)
    return stats_text


def coc7stats(_, update: Update, args: List[str]):
    message = update.message
    assert isinstance(message, telegram.Message)

    if len(args) == 0:
        age = None
    elif len(args) != 1 or not args[0].isnumeric():
        message.reply_text(
            "召唤方式错误哦，只需要跟一个年龄参数，像这样 `/coc7 18` 。",
            parse_mode='Markdown'
        )
        return
    else:
        age = int(args[0])

    message.reply_text(coc7stats_text(age), parse_mode='Markdown')


DICE_TYPE_PATTERN = re.compile(r'^d(\d+)')


def set_default_dice(_, update: Update, args: [str], chat_data: dict):
    message = update.message
    assert isinstance(message, telegram.Message)

    # 没有参数
    if len(args) != 1:
        message.reply_text(
            "诶呀，召唤我的方式出错了! `/set_dice` 后面跟一个形如 `d100` 的哦",
            parse_mode='Markdown'
        )
        return

    arg = args[0]
    normal = DICE_TYPE_PATTERN.match(arg)
    if normal is not None:
        face_num = int(normal.group(1))
        if face_num > MAX_FACE:
            message.reply_text("骰子的面数太多了，你在想什么！")
        chat_data['dice'] = Dice(face_num)
        message.reply_text("已设定当前默认骰子为{}面骰".format(face_num))
    else:
        message.reply_text("这种类型的骰子没办法设为默认骰子")


DICE_ROLL_PATTERN = re.compile(r'^(\d+)d(\d+)$')


def command_roll(_, update: Update, args: [str], chat_data: dict):
    msg = update.message
    assert isinstance(msg, telegram.Message)
    _, text = dice.roll(' '.join(args), chat_data.get('dice', 100))
    msg.reply_text(text, parse_mode='HTML')


def coc_trait(_, update: Update):
    msg = update.message
    assert isinstance(msg, telegram.Message)

    belief = [
        '你信仰并祈并一位大能。(例如毗沙门天、耶稣基督、海尔·塞拉西一世)',
        '人类无需上帝。(例如坚定的无神论者，人文主义者，世俗主义者)',
        '科学万能!科学万岁!你将选择其中之一。(例如进化论，低温学，太空探索)',
        '命中注定。(例如因果报应，种姓系统，超自然存在)',
        '社团或秘密结社的一员。(例如共济会，女协，匿名者)',
        '社会坏掉了，而你将成为正义的伙伴。应斩除之物是？(例如毒品，暴力，种族歧视)',
        '神秘依然在。(例如占星术，招魂术，塔罗)',
        '键盘政治局委员。(例如保守党，共产党，自由党)',
        '“金钱就是力量，我的朋友，我将竭尽全力获取我能看到的一切。”(例如贪婪心，进取心，冷酷心)',
    ]

    vip_who = [
        "你的父辈。(例如母亲，父亲，继母)",
        "你的祖父辈。(例如外祖母、祖父)",
        "你的兄弟姐妹。(例如妹妹、半血亲妹妹、无血缘妹妹、表妹)",
        "你的孩子。(儿子或女儿)",
        "你的另一半。(例如配偶，未婚夫，爱人)",
        "那位指引你人生技能的人。指明该技能和该人。(例如学校教师，师傅，父亲)",
        "你自幼熟识的人。(例如同学，邻居，幼驯染)",
        "一位名人、偶像或者英雄。当然也许你从未见过他。 (例如电影明星，政治家，音乐家。)",
        "游戏中的另一位调查员伙伴。随机或自选。",
        "游戏中另一位NPC。详情咨询你的守秘人。",
    ]

    vip_why = [
        "你欠了他们人情。他们帮助了你什么？(例如， 经济上，困难时期的庇护，给你第一份工作)",
        "他们教会了你一些东西。(例如，技能，如何去爱，如何成为男子汉)",
        "他们给了你生命的意义。(例如，你渴望成为他们 那样的人，你苦苦追寻着他们，你想让他们高兴)",
        "你曾害了他们，而现在寻求救赎。例如，偷窃了他们的钱财，向警方报告了他们的行踪，在他们绝望时拒绝救助)",
        "同甘共苦。(例如，你们共同经历过困难时期，你们携手成长，共同度过战争)",
        "你想向他们证明自己。(例如，自己找到工作，自己搞到老婆，自己考到学历)",
        "你崇拜他们。(例如，崇拜他们的名头，他们的魅力，他们的工作)",
        "后悔的感觉。(例如，你本应死在他们面前，你背弃了你的誓言，你在可以助人之时驻足不前)",
        "你试图证明你比他们更出色。他们的缺点是? (例如，懒惰，酗酒，冷漠)",
        "他们扰乱了你的人生，而你寻求复仇。发生了什么？(例如，射杀爱人之日，国破家亡之时，明镜两分之际)",
    ]

    place = [
        "你最爱的学府。(例如，中学，大学)",
        "你的故乡。(例如，乡下老家，小镇村，大都市)",
        "相识初恋之处。(例如，音乐会，度假村，核弹避难所)",
        "静思之地。(例如，图书馆，你的乡土别墅，钓鱼中)",
        "社交之地。(例如，绅士俱乐部，地方酒吧，叔叔的家)",
        "联系你思想 / 信念的场所。(例如，小教堂，麦加， 巨石阵)",
        "重要之人的坟墓。(例如，另一半，孩子，爱人)",
        "家族所在。(例如，乡下小屋，租屋，幼年的孤儿院)",
        "生命中最高兴时的所在。(例如，初吻时坐着的公园长椅，你的大学)",
        "工作地点。(例如，办公室，图书馆，银行)",
    ]

    treasure = [
        "与你得意技相关之物。(例如华服，假ID卡，青铜指虎)",
        "职业必需品。(例如医疗包，汽车，撬锁器)",
        "童年的遗留物。(例如漫画书，随身小刀，幸运币)",
        "逝者遗物。(例如烛堡，钱包里的遗照，信)",
        "重要之人给予之物。(例如戒指，日志，地图)",
        "收藏品。(例如撤票，标本，记录)",
        "你发掘而不知真相的东西。答案追寻中。(例如， 橱柜里找到的未知语言信件，一根奇怪的从父亲出继承来的来源不明的风琴，花园里挖出来的奇妙的银球)",
        "体育用品。(例如，球棒，签名棒球，鱼竿)",
        "武器。(例如，半自动左轮，老旧的猎用来福，靴刃)",
        "宠物。(例如狗，猫，乌龟)",
    ]

    trait = [
        "慷慨大方。(例如，小费大手，及时雨，慈善家)",
        "善待动物。(例如，爱猫人士，农场出生，与小马同舞)",
        "梦想家。(例如，惯常异想天开，预言家，创造者)",
        "享乐主义者。(例如，派对大师，酒吧醉汉，“放纵到死”)",
        "赌徒，冒险家。(例如，扑克脸，任何事都来一遍，活在生死边缘)",
        "好厨子，好吃货。(例如，烤得一手好蛋糕，无米之炊都能做好，优雅的食神)",
        "女人缘 / 万人迷。(例如，长袖善舞，甜言蜜语，电眼乱放)",
        "忠心在我。(例如，背负自己的朋友，从未破誓， 为信念而死)",
        "好名头。(例如，村里最好的饭后聊天人士，虔信圣徒，不惧任何危险)",
        "雄心壮志。(例如，梦想远大，目标是成为BOSS，渴求一切)",
    ]
    constellation = (u'摩羯座', u'水瓶座', u'双鱼座', u'白羊座', u'金牛座', u'双子座', u'巨蟹座', u'狮子座', u'处女座', u'天秤座', u'天蝎座', u'射手座')
    blood_types = ('A', 'B', 'AB', 'O')
    rh_positive = secrets.randbelow(20) == 4  # 1/20 的几率
    blood_type = choice(blood_types)
    if rh_positive:
        blood_type += '/Rh-'
    wuxing = ('金', '木', '水', '火', '土')
    mbti_list = (('E', 'I'), ('S', 'N'), ('T', 'F'), ('J', 'P'))
    mbti = ''.join(map(choice, mbti_list))
    luck_number = list(map(lambda x: x + 1, range(20))) + [42]

    characters_war_list = (('明日香', '绫波丽', '美里'), ('冬马', '雪菜'), ('02', '015'), ('养鸡', '养女'))
    characters_war_result = '/'.join(map(choice, characters_war_list))
    message = '''自动生成的人物特征，仅供参考，部分采纳，不要照单全收。
你的[信念]： {}
你生命中[最重要的人]，就是{} 因为{}
对你来说最[意义非凡的地点]是{}
你的[珍宝]是{}
你常常被人形容为{}
你的星座是{} 血型是{} 幸运数字是{}
有道士说你命格为{} 命中缺{} 最近有{}难
你做 MBTI 测试的结果是 {}
如果看到那些作品的话，你会更喜欢 {}
    '''.format(choice(belief), choice(vip_who), choice(vip_why), choice(place),
               choice(treasure), choice(trait), choice(constellation), blood_type,
               choice(luck_number), choice(wuxing), choice(wuxing), choice(wuxing),
               mbti, characters_war_result)
    msg.reply_text(message)


def select(_, update: Update, args: [str]):
    message = update.message
    assert isinstance(message, telegram.Message)
    message.reply_text(choice(args))


LOCALE_NAME = {
    '英': 'en_GB',
    '英国': 'en_GB',
    '美': 'en_GB',
    '美国': 'en_US',
    '德': 'de_DE',
    '德国': 'de_DE',
    '中': 'zh_CN',
    '中国': 'zh_CN',
    '大陆': 'zh_CN',
    '台': 'zh_TW',
    '台湾': 'zh_TW',
    '日': 'ja_JP',
    '日本': 'ja_JP',
    '法': 'fr_FR',
    '法国': 'fr_FR',
    '韩': 'ko_KR',
    '韩国': 'ko_KR',
    '韓国': 'ko_KR',
}


def random_text(method_name):
    def command(_, update, args):
        message = update.message
        assert isinstance(message, telegram.Message)
        locale = 'zh_CN'
        if len(args) > 0:
            name = args[0]
            name.replace('國', '国')
            locale = LOCALE_NAME.get(name, name)
        try:
            fake = Faker(locale)
        except AttributeError:
            message.reply_text(
                '地区参数错误，如「中国」、「日本」、「美国」'
                '或「中」、「日」、「美」，或者在[这个页面]'
                '(https://github.com/joke2k/faker)里找。',
                parse_mode='Markdown',
            )
            return

        result = []
        method = getattr(fake, method_name)
        for _ in range(20):
            result.append(method())
        message.reply_text(', '.join(result))

    return command


def inline_query(_, update):
    """Handle the inline query."""
    query = update.inline_query.query
    assert isinstance(query, str)
    query = query.strip()
    _, text = dice.roll(query, 20)
    if query.find(',') != -1:
        choice_item = query.split(',')
    elif query.find('，') != -1:
        choice_item = query.split('，')
    else:
        choice_item = query.split()
    choice_item = list(filter(lambda s: s != '', map(lambda s: s.strip(), choice_item)))
    if choice_item:
        choice_result = choice(choice_item)
        choice_result = '<code>{}</code> → {}'.format(', '.join(choice_item), choice_result)
    else:
        choice_result = None

    if len(choice_item) == 1:
        choice_result += '\n\n只有一个选项，还让我选个蛋蛋哦?'

    stats = '生成角色得写年龄呐! 别写乱七八糟的'
    if query.isnumeric() and len(query) < 3:
        age = int(query)
        stats = coc7stats_text(age)
    elif query == '':
        stats = coc7stats_text(None)

    results = []
    if choice_result:
        results.append(InlineQueryResultArticle(
            id=uuid4(),
            title="选择一项",
            description="有烦恼？让本小姐帮你决断吧！用空格分开选项如「睡觉 学习 赞美骰子女神」",
            input_message_content=InputTextMessageContent(choice_result, parse_mode=ParseMode.HTML),
        ))

    results += [
        InlineQueryResultArticle(
            id=uuid4(),
            title="投骰子",
            description="XdY X为骰子个数，Y为骰子面数，默认为20面",
            input_message_content=InputTextMessageContent(text, parse_mode=ParseMode.HTML),
        ),
        InlineQueryResultArticle(
            id=uuid4(),
            title="CoC 7E 人物属性",
            description="刷屏注意。另外记得写上年龄!",
            input_message_content=InputTextMessageContent(stats, parse_mode=ParseMode.MARKDOWN),
        ),
    ]

    update.inline_query.answer(results, cache_time=0)


def dnd5e_modifiers(point: int):
    result = point // 2 - 5
    if result > 0:
        return '+{}'.format(result)
    else:
        return str(result)


def dnd5e_attributes(_, update: telegram.Update):
    message = update.message
    assert isinstance(message, telegram.Message)
    d6 = Dice(6)
    result = []
    for _ in range(6):
        roll_4 = d6.roll_n(4)
        roll_4.sort()
        point = sum(roll_4[1:])
        result.append('{} ({})'.format(point, dnd5e_modifiers(point)))
    text = '将下面六项数值自由分配到\n' \
           '力量(STR) 敏捷(DEX) 体质(CON) ' \
           '智力(INT) 感知(WIS) 魅力(CHA) 中\n\n' \
           '{}'.format(', '.join(result))
    message.reply_text(text)


def error(_, update, err):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, err)


def main():
    updater = Updater(token=TOKEN)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler('r', command_roll, pass_args=True, pass_chat_data=True))
    dispatcher.add_handler(CommandHandler('coc7', coc7stats, pass_args=True))
    dispatcher.add_handler(CommandHandler('dnd5e', dnd5e_attributes))
    dispatcher.add_handler(CommandHandler('coctrait', coc_trait))
    dispatcher.add_handler(CommandHandler('name', random_text('name'), pass_args=True))
    dispatcher.add_handler(CommandHandler('male', random_text('name_male'), pass_args=True))
    dispatcher.add_handler(CommandHandler('female', random_text('name_female'), pass_args=True))
    dispatcher.add_handler(CommandHandler('company', random_text('company'), pass_args=True))
    dispatcher.add_handler(CommandHandler('address', random_text('address'), pass_args=True))
    dispatcher.add_handler(CommandHandler('city', random_text('city'), pass_args=True))
    dispatcher.add_handler(CommandHandler('decide', select, pass_args=True))
    dispatcher.add_handler(CommandHandler('choice', select, pass_args=True))
    dispatcher.add_handler(CommandHandler('select', select, pass_args=True))
    dispatcher.add_handler(InlineQueryHandler(inline_query))
    dispatcher.add_error_handler(error)

    # Start the Bot
    if 'WEBHOOK_URL' in os.environ:
        updater.start_webhook(listen='0.0.0.0', port=9991, url_path=TOKEN)
        url = os.path.join(os.environ['WEBHOOK_URL'], TOKEN)
        updater.bot.set_webhook(url=url)
    else:
        updater.start_polling()

    updater.idle()


if __name__ == '__main__':
    main()
