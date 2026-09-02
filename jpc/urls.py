from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from .views import public_media


urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("media/<path:path>", public_media, name="public-media"),
    path("", include("partners.urls")),
]
