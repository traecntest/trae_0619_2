from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FocusSessionViewSet,
    register_view,
    login_view,
)

router = DefaultRouter()
router.register(r"sessions", FocusSessionViewSet, basename="session")

urlpatterns = [
    path("auth/register/", register_view, name="register"),
    path("auth/login/", login_view, name="login"),
    path("", include(router.urls)),
]
