from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.cinema import urls as cinema_urls
from apps.movie import urls as movie_urls
from apps.user import urls as user_urls

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/users/", include(user_urls)),
    path("api/movies/", include(movie_urls)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/schema/swagger-ui/",
         SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/cinemas/", include(cinema_urls)),
]
