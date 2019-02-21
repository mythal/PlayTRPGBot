from django.contrib import admin

from .models import Log, Chat


@admin.register(Log)
class LogAdmin(admin.ModelAdmin):
    date_hierarchy = 'created'
    list_filter = ('chat', 'deleted')
    list_display = ('chat', 'character_name', 'content', 'created')
    list_display_links = ('content',)
    search_fields = ('chat__title', 'content')
    list_per_page = 1024


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    date_hierarchy = 'created'
    list_display = ('title', 'created')
    list_display_links = ('title',)
    search_fields = ('title',)
