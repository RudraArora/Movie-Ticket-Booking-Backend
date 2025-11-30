from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.cinema import constants as cinema_constants, models as cinema_models
from apps.movie import models as movie_models


class LocationSerializer(serializers.ModelSerializer):
    """
    Serializer for the Location model.

    Handles the conversion of Location model instances to and from
    JSON representations for API transport.
    """

    class Meta:
        model = cinema_models.Location
        fields = ["city"]


class CinemaSerializer(serializers.ModelSerializer):
    """
    Serializer for the Cinema model.

    Handles the conversion of Cinema model instances to and from
    JSON representations for API transport.
    """

    location = serializers.SlugRelatedField(slug_field="city", read_only=True)

    class Meta:
        model = cinema_models.Cinema
        fields = ["id", "name", "location", "rows", "seats_per_row", "slug"]


class SeatAvailabilitySerializer(serializers.ModelSerializer):
    """
    Serializer for seat availaiblity.

    Handles the conversion of Cinema Seat model instances to and from
    JSON representations.
    """

    available = serializers.BooleanField()

    class Meta:
        model = cinema_models.CinemaSeat
        fields = ["id", "row_number", "seat_number", "available"]


class SlotSerializer(serializers.ModelSerializer):
    """
    Serializer for Slot Model.
    Converts slot model instances to/from JSON.
    """

    class Meta:
        model = cinema_models.Slot
        fields = ["start_time", "end_time", "price", "end_time"]


class CinemaMovieSlotSerializer(serializers.ModelSerializer):
    """
    Serializer for CinemaMovieSlots.
    Convert python objects to/from JSON, and also add
    'slots' field in movie model (by reverse relation).
    """

    slots = SlotSerializer(many=True)
    languages = serializers.SlugRelatedField(
        many=True, slug_field="language", read_only=True
    )

    class Meta:
        model = movie_models.Movie
        fields = ["id", "name", "languages", "duration", "slots"]


class MovieCinemaSlotSerializer(serializers.ModelSerializer):
    location = serializers.SlugRelatedField(slug_field="city", read_only=True)
    slots = SlotSerializer(many=True)

    class Meta:
        model = cinema_models.Cinema
        fields = ["id", "name", "location", "rows", "seats_per_row", "slots"]


class BookingSeatSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a seat booking.
    - Validates seat IDs, slot existence, and booking conflicts.
    - Creates Booking and BookingSeat entries on success.
    """

    seat_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True)

    def validate(self, attrs):
        slot_id = self.context["view"].kwargs.get("slot_id")
        seat_ids = attrs.get("seat_ids")

        try:
            slot = cinema_models.Slot.objects.get(id=slot_id)
        except cinema_models.Slot.DoesNotExist:
            raise NotFound(cinema_constants.ErrorMessage.SLOT_NOT_FOUND)

        valid_seats = cinema_models.CinemaSeat.objects.filter(id__in=seat_ids).filter(
            cinema_id=slot.cinema
        )

        if valid_seats.count() != len(seat_ids):
            raise ValidationError(cinema_constants.ErrorMessage.INVALID_SEAT)

        booked_seats = cinema_models.BookingSeat.objects.filter(
            booking__slot_id=slot_id,
            cinema_seat__in=seat_ids,
            booking__status=cinema_constants.BookingStatus.BOOKED.value,
        )

        if booked_seats:
            raise ValidationError(
                {
                    cinema_constants.ErrorMessage.BOOKED_SEAT,
                }
            )

        if slot.start_time < timezone.now():
            raise PermissionDenied(cinema_constants.ErrorMessage.PAST_BOOKING_BOOKED)

        attrs["slot"] = slot
        return super().validate(attrs)

    class Meta:
        model = cinema_models.Booking
        fields = ["id", "seat_ids"]

    def create(self, validated_data):
        slot = validated_data["slot"]
        booking = cinema_models.Booking.objects.create(
            user=self.context["request"].user,
            slot=slot,
            status=cinema_constants.BookingStatus.BOOKED.value,
        )

        seat_ids = validated_data["seat_ids"]
        booking_seats = [
            cinema_models.BookingSeat(cinema_seat_id=seat_id, booking=booking)
            for seat_id in seat_ids
        ]

        cinema_models.BookingSeat.objects.bulk_create(booking_seats)
        return booking


class BookingCancelSerializer(serializers.Serializer):
    """
    Serializer for cancelling a booking.
    Validates:
    - Booking exists
    - Booking belongs to the logged-in user
    - Booking is not already cancelled
    """

    def validate(self, attrs):
        booking_id = self.context["view"].kwargs["booking_id"]
        user = self.context["request"].user
        # Check if booking exists
        try:
            booking = cinema_models.Booking.objects.get(id=booking_id, user_id=user.id)
        except cinema_models.Booking.DoesNotExist:
            raise ValidationError(cinema_constants.ErrorMessage.BOOKING_NOT_EXIST)

        if booking.status == cinema_constants.BookingStatus.CANCELLED.value:
            raise ValidationError(cinema_constants.ErrorMessage.BOOKING_CANCEL)

        if booking.slot.start_time < timezone.now():
            raise PermissionDenied(cinema_constants.ErrorMessage.PAST_BOOKING)

        attrs["booking"] = booking
        return attrs

    def create(self, validated_data):
        booking = validated_data["booking"]
        booking.status = cinema_constants.BookingStatus.CANCELLED.value
        booking.save()
        return booking
