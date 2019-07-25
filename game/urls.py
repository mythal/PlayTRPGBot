from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register(r'variables', views.VariableViewSet)
router.register(r'players', views.PlayerViewSet)

urlpatterns = router.urls
