from django import template

from ..models import Log
from entities import Entities

register = template.Library()


def log_entities(value: Log):
    return Entities.from_object(value.entities).html().replace('/n', '<br>')


register.filter('log_entities', log_entities)


@register.simple_tag(takes_context=True)
def url_replace(context, field, value):
    dict_ = context['request'].GET.copy()
    dict_[field] = value
    return dict_.urlencode()
