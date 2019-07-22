from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def url_replace(context, field, value):
    dict_ = context['request'].GET.copy()
    dict_[field] = value
    return dict_.urlencode()


@register.filter
def counter_6(xs: list):
    return xs.count(6)
