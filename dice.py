import secrets

from pypeg2 import *


class RollError(RuntimeError):
    pass


class Env:
    def __init__(self, face=100):
        self.face = face


class Number(Symbol):
    regex = re.compile(r'\d{1,4}')

    def eval(self):
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

    def eval(self, env: Env, show_sum=True):
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
        if show_sum:
            show += '={}'.format(sum(result))
        return result, show


class Max:
    grammar = 'max', '(', attr('dice', Dice), ')'

    def eval(self, env):
        value, text = self.dice.eval(env, show_sum=False)
        result = max(value)
        return result, 'max({})={}'.format(text, result)


class Min:
    grammar = 'min', '(', attr('dice', Dice), ')'

    def eval(self, env):
        value, text = self.dice.eval(env, show_sum=False)
        result = min(value)
        return result, 'min({})={}'.format(text, min(value))


# left recursion!
# https://bitbucket.org/fdik/pypeg/issues/4/
class Expr(List):
    def eval(self, env):
        add = Add('+')
        op = add
        acc = 0
        show_list = []
        for i in self:
            v = 0
            if isinstance(i, Dice):
                v, show = i.eval(env)
                v = sum(v)
                show_list.append(show)
            elif isinstance(i, Max) or isinstance(i, Min):
                v, show = i.eval(env)
                show_list.append(show)
            elif isinstance(i, Number):
                v, show = i.eval()
                show_list.append(show)
            elif isinstance(i, Expr):
                v, show = i.eval(env)
                show_list.append(show)

            if isinstance(i, Operator):
                show_list.append(i.display)
                op = i
            else:
                if isinstance(op, Add):
                    acc += v
                elif isinstance(op, Mul):
                    acc *= v
                    op = add
                elif isinstance(op, Sub):
                    acc -= v
                    op = add
                elif isinstance(op, Div):
                    try:
                        acc = acc // v
                    except ZeroDivisionError:
                        raise RollError('要知道，0 不能做除数')
                    op = add

        return acc, '[{}]={}'.format(' '.join(show_list), acc)


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
            value, text = parse('1d', Dice).eval(env)
            result_value = sum(value)
            result_text.insert(0, '<code>{}</code>'.format(text))
        return result_value, ' '.join(result_text)


def roll(text, default_dice_face):
    env = Env(face=default_dice_face)
    try:
        roll_ast = parse(text, Roll)
    except SyntaxError:
        raise RollError('格式错误!')
    return roll_ast.eval(env)
