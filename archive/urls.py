from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('chat/<int:chat_id>/', views.chat, name='chat'),
    path('chat/<int:chat_id>/tag/<int:tag_id>/', views.chat, name='chat'),
    path('chat/<int:chat_id>/<str:_title>.<str:method>', views.export, name='export'),
    path('chat/<int:chat_id>/please_input_password', views.require_password, name='require_password')
]
