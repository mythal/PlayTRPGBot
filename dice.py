import secrets

from pypeg2 import *


class RollError(RuntimeError):
    pass


class Env:
    def __init__(self, face=100):
        self.face = face


class Number(Symbol):
    regex = re.compile(r'\d{1,4}')

    def eval(self, *_args):
        return int(self.name), self.name


class Operator(Symbol):
    display = ''


class Add(Operator):
    regex = re.compile(r'\+')
    display = '+'


class Sub(Operator):
    regex = re.compile(r'-')
    display = '-'


class Mul(Operator):
    regex = re.compile(r'[*×]')
    display = '×'


class Div(Operator):
    regex = re.compile(r'[/÷]')
    display = '÷'


operator = [Add, Sub, Mul, Div]


class Dice:
    grammar = attr('counter', optional(Number)), 'd', attr('face', optional(Number))

    def eval(self, env: Env, result_sum=True):
        if self.face:
            face, _ = self.face.eval()
        else:
            face = env.face
        if self.counter:
            counter, _ = self.counter.eval()
        else:
            counter = 1

        if face == 0 or counter == 0:
            result = [0]
        elif face == 1:
            result = [1 for _ in range(counter)]
        else:
            result = [secrets.randbelow(face) + 1 for _ in range(counter)]
        if len(result) > 6:
            result_text = '={...}'
        elif counter < 2:
            result_text = ''
        else:
            result_text = '={{{}}}'.format(', '.join(map(str, result)))
        show = '{}d{}{}'.format(counter, face, result_text)
        if result_sum:
            result = sum(result)
            show += '={}'.format(result)
        return result, show


class Max:
    grammar = 'max', '(', attr('dice', Dice), ')'

    def eval(self, env):
        value, text = self.dice.eval(env, result_sum=False)
        result = max(value)
        return result, 'max({})={}'.format(text, result)


class Min:
    grammar = 'min', '(', attr('dice', Dice), ')'

    def eval(self, env):
        value, text = self.dice.eval(env, result_sum=False)
        result = min(value)
        return result, 'min({})={}'.format(text, min(value))


# left recursion!
# https://bitbucket.org/fdik/pypeg/issues/4/
class Expr(List):
    def eval(self, env):
        value_list = []
        show_list = []

        for i in self:
            if not isinstance(i, Operator):
                v, show = i.eval(env)
                value_list.append(v)
                show_list.append(show)
            else:
                show_list.append(i.display)
                value_list.append(i)

        for i, current in enumerate(value_list):
            if isinstance(current, (Mul, Div)):
                a = value_list[i - 1]
                b = value_list[i + 1]
                if isinstance(current, Mul):
                    value_list[i + 1] = a * b
                elif b == 0:
                    raise RollError('要知道，0 不能做除数')
                else:
                    value_list[i + 1] = a // b
                value_list[i] = None
                value_list[i - 1] = None
        value_list = list(filter(lambda x: x is not None, value_list))
        result = value_list[0]
        for i, current in enumerate(value_list):
            if isinstance(current, Add):
                result += value_list[i + 1]
            elif isinstance(current, Sub):
                result -= value_list[i + 1]
        return result, '[{}]={}'.format(' '.join(show_list), result)


item = [Dice, Number, Max, Min, ('(', Expr, ')')]
Expr.grammar = (item, maybe_some(operator, item))


class Roll(List):
    grammar = maybe_some([Expr, re.compile(r'\S+')])

    def eval(self, env):
        expr_count = 0
        result_value = 0
        result_text = []
        for e in self:
            if isinstance(e, str):
                result_text.append(e)
            else:
                value, text = e.eval(env)
                result_value = value
                expr_count += 1
                result_text.append('<code>{}</code>'.format(text))
        if expr_count == 0:
            result_value, text = parse('1d', Dice).eval(env)
            result_text.insert(0, '<code>{}</code>'.format(text))
        return result_value, ' '.join(result_text)


def roll(text, default_dice_face):
    env = Env(face=default_dice_face)
    try:
        roll_ast = parse(text, Roll)
    except SyntaxError:
        raise RollError('格式错误!')
    return roll_ast.eval(env)
