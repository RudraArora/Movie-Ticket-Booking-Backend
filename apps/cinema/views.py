from datetime import datetime

from django.db.models import Case, Prefetch, When
from django.utils import timezone
from rest_framework import exceptions, generics, permissions, response, status, viewsets

from apps.cinema import (
    constants as cinema_constants,
    filters as cinema_filters,
    models as cinema_models,
    serializers as cinema_serializers,
)
from apps.common import pagination as common_pagination
from apps.movie import models as movie_models


class CinemaView(generics.ListAPIView):
    """
    Cinema list view with location filter
    """

    serializer_class = cinema_serializers.CinemaSerializer
    pagination_class = common_pagination.CustomCursorPagination

    def get_queryset(self):
        queryset = cinema_models.Cinema.objects.select_related("location")
        manager = cinema_filters.CinemaFilterManager()
        return manager.apply_filters(self.request, queryset)


class CinemaSpecificView(generics.RetrieveAPIView):
    """
    Specific cinema view
    """

    queryset = cinema_models.Cinema.objects.all()
    serializer_class = cinema_serializers.CinemaSerializer
    lookup_field = "slug"


class LocationView(generics.ListAPIView):
    """
    Location list View
    """

    queryset = cinema_models.Location.objects.all()
    serializer_class = cinema_serializers.LocationSerializer


class SeatAvailabilityView(generics.ListAPIView):
    """
    View for finding the seat availaibility
    """

    serializer_class = cinema_serializers.SeatAvailabilitySerializer

    def get_queryset(self):
        slot_id = self.kwargs["slot_id"]
        cinema_id = self.kwargs["cinema_id"]

        if not cinema_models.Cinema.objects.filter(id=cinema_id).exists():
            raise exceptions.NotFound(cinema_constants.ErrorMessage.CINEMA_NOT_EXIST)

        if not cinema_models.Slot.objects.filter(id=slot_id).exists():
            raise exceptions.NotFound(cinema_constants.ErrorMessage.SLOT_NOT_FOUND)

        if not cinema_models.Slot.objects.filter(id=slot_id, cinema=cinema_id).exists():
            raise exceptions.ValidationError(
                cinema_constants.ErrorMessage.SLOT_NOT_BELONG_CINEMA
            )

        booked_seats = cinema_models.BookingSeat.objects.filter(
            booking__slot__cinema=cinema_id,
            booking__slot_id=slot_id,
            booking__status=cinema_constants.BookingStatus.BOOKED.value,
        ).values_list("cinema_seat", flat=True)

        queryset = cinema_models.CinemaSeat.objects.filter(
            cinema_id=cinema_id
        ).annotate(available=Case(When(id__in=booked_seats, then=False), default=True))

        return queryset


class CinemaMovieSlotView(generics.ListAPIView):
    """
    View for finding all the slots for a specific cinema
    """

    serializer_class = cinema_serializers.CinemaMovieSlotSerializer
    pagination_class = common_pagination.CustomCursorPagination

    def get_queryset(self):
        """
        Function which filter the slots of given date.
        then attach them in their respective cinema data.
        """

        cinema_id = self.kwargs["cinema_id"]

        date = self.request.query_params.get("date")

        if not date:
            raise exceptions.ValidationError(
                cinema_constants.ErrorMessage.DATE_PARAM_REQUIRED
            )
        else:
            try:
                date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                raise exceptions.ValidationError(
                    cinema_constants.ErrorMessage.INVALID_DATE_FORMAT
                )

        if not cinema_models.Cinema.objects.filter(id=cinema_id).exists():
            raise exceptions.NotFound(cinema_constants.ErrorMessage.CINEMA_NOT_EXIST)

        now = timezone.localtime(timezone.now())

        if date == now.date():
            slots_qs = cinema_models.Slot.objects.filter(
                cinema_id=cinema_id, start_time__gte=now
            )
        else:
            slots_qs = cinema_models.Slot.objects.filter(
                cinema_id=cinema_id, start_time__date=date
            )

        return (
            movie_models.Movie.objects.filter(slot__in=slots_qs)
            .distinct()
            .prefetch_related(Prefetch("slot_set", queryset=slots_qs, to_attr="slots"))
        )


class BookingViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return cinema_serializers.BookingCancelSerializer
        elif self.request.method == "POST":
            return cinema_serializers.BookingSeatSerializer

    def partial_update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return response.Response(status=status.HTTP_204_NO_CONTENT)
