from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('chat/<int:chat_id>/', views.chat, name='chat'),
    path('chat/<int:chat_id>/export/<str:method>', views.export, name='export'),
]