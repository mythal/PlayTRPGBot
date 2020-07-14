from django.urls import path

from . import views


urlpatterns = [
    path('', views.index, name='index'),
    path('chat/<int:chat_id>/', views.chat_page, name='chat'),
    path('chat/<int:chat_id>/variables', views.variables, name='variables'),
    path('chat/<int:chat_id>/variables/edit/<int:variable_id>', views.edit_variables, name='edit_variable'),
    path('chat/<int:chat_id>/variables/create', views.edit_variables, name='create_variable'),
    path('chat/<int:chat_id>/log.<str:method>', views.export, name='export'),
    path('chat/<int:chat_id>/please_input_password', views.require_password, name='require_password'),
]

