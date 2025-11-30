from django.urls import path

from apps.cinema import views as cinema_views

urlpatterns = [
    path("", cinema_views.CinemaView.as_view(), name="cinemas"),
    path("locations/", cinema_views.LocationView.as_view(), name="locations"),
    path(
        "<slug:slug>/", cinema_views.CinemaSpecificView.as_view(), name="cinema_detail"
    ),
    path(
        "<int:cinema_id>/slots/<int:slot_id>/seats/",
        cinema_views.SeatAvailabilityView.as_view(),
        name="available_seats",
    ),
    path(
        "<int:cinema_id>/movie-slots/",
        cinema_views.CinemaMovieSlotView.as_view(),
        name="cinema_movie_slots",
    ),
    path(
        "movie-slots/<int:slot_id>/bookings/",
        cinema_views.BookingViewSet.as_view(
            {
                "post": "create",
            }
        ),
        name="booking_seat",
    ),
    path(
        "bookings/<int:booking_id>/",
        cinema_views.BookingViewSet.as_view(
            {
                "patch": "partial_update",
            }
        ),
        name="booking_cancel",
    ),
]
