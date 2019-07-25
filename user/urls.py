from django.urls import path

from . import views

urlpatterns = [
    path('telegram-login/', views.telegram_login, name='telegram_login'),
    path('logout/', views.logout_page, name='logout'),
]