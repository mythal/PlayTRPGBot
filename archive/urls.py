from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('chat/<int:chat_id>/', views.chat_page, name='chat'),
    path('chat/<int:chat_id>/<str:_title>.<str:method>', views.export, name='export'),
    path('chat/<int:chat_id>/please_input_password', views.require_password, name='require_password'),
    path('telegram-login/', views.telegram_login, name='telegram_login'),
    path('logout/', views.logout, name='logout'),
]
