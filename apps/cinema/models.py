from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models as db_models
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify

from apps.cinema import constants as cinema_constants
from apps.common import models as common_models
from apps.movie import models as movie_models

User = get_user_model()


class Location(db_models.Model):
    """
    Model for the location that a cinema belongs to
    """

    city = db_models.CharField(
        max_length=cinema_constants.MaxLength.LOCATION, unique=True
    )

    def clean(self):
        self.city = self.city.lower().strip()

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.city


class Cinema(common_models.TimeStampModel):
    """
    Models a cinema with its layout and location.

    Attributes:
    -----------
        name: The name of the cinema.
        rows: The number of seating rows.
        seats_per_row: The number of seats in each row.
        location: The physical location of the cinema.
        slug: A unique identifier, automatically generated from the
            cinema's name and location.
    """

    name = db_models.CharField(max_length=cinema_constants.MaxLength.NAME)
    location = db_models.ForeignKey(Location, on_delete=db_models.CASCADE)
    rows = db_models.PositiveIntegerField()
    seats_per_row = db_models.PositiveIntegerField()
    slug = db_models.SlugField(unique=True, blank=True, help_text=cinema_constants.HelpText.SLUG)

    class Meta:
        constraints = [
            db_models.UniqueConstraint(
                fields=["name", "location"], name="unique_name_location"
            )
        ]

    def clean(self):
        if not self.slug:
            self.slug = slugify(f"{self.name}-{self.location}")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.slug


class CinemaSeat(db_models.Model):
    """
    Represents a CinemaSeat of the particular cinema.
    """

    row_number = db_models.PositiveSmallIntegerField()
    seat_number = db_models.PositiveSmallIntegerField()
    cinema_id = db_models.ForeignKey(Cinema, on_delete=db_models.CASCADE)

    def __str__(self):
        return f"{self.cinema_id.slug} - R{self.row_number} S{self.seat_number}"


@receiver(db_models.signals.post_save, sender=Cinema)
def create_seats_after_cinema_save(sender, instance, created, **kwargs):
    if not created:
        return

    seats = []

    if not CinemaSeat.objects.filter(cinema_id=instance.id).exists():
        for row_index in range(1, instance.rows + 1):
            for seat_num in range(1, instance.seats_per_row + 1):
                seats.append(
                    CinemaSeat(
                        cinema_id=instance, row_number=row_index, seat_number=seat_num
                    )
                )

        CinemaSeat.objects.bulk_create(seats)


class Slot(common_models.TimeStampModel):
    """
    Represents a showtime for a movie in a cinema.
    - Stores date, start time and ticket price.
    - Validates that the slot is not in the past and does not overlap with other slots in the same cinema.
    """
    cinema = db_models.ForeignKey(Cinema, on_delete=db_models.CASCADE)
    movie = db_models.ForeignKey(
        movie_models.Movie, on_delete=db_models.CASCADE)
    start_time = db_models.DateTimeField(
        help_text=cinema_constants.HelpText.START_TIME
    )
    end_time = db_models.DateTimeField(
        blank=True,
        help_text=cinema_constants.HelpText.AUTO_GENERATE
    )
    price = db_models.DecimalField(max_digits=8, decimal_places=2)

    def clean(self):
        self.end_time = self.start_time + self.movie.duration

        if self.start_time <= timezone.now():
            raise ValidationError(
                cinema_constants.ErrorMessage.SLOT_PAST_SCHEDULE
            )

        if self.start_time.date() < self.movie.release_date:
            raise ValidationError(
                cinema_constants.ErrorMessage.INVALID_SLOT_DATE
            )

        overlapping_slots = Slot.objects.filter(
            db_models.Q(start_time__lte=self.start_time, end_time__gte=self.start_time, cinema=self.cinema) |
            db_models.Q(start_time__lte=self.end_time,
                        end_time__gte=self.end_time, cinema=self.cinema) 
        )

        if overlapping_slots.exists():
            raise ValidationError(
                cinema_constants.ErrorMessage.SLOT_OVERLAPS
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.movie.name}-{self.cinema.name}-{self.start_time}"


class Booking(common_models.TimeStampModel):
    """
    Represents a user's booking for a slot.
    - Stores booking status (Booked/Cancelled).
    - Linked to a user and a slot.
    """
    SEAT_STATUS_CHOICES = [("B", "Booked"), ("C", "Cancelled")]
    status = db_models.CharField(max_length=1, choices=SEAT_STATUS_CHOICES)
    user = db_models.ForeignKey(User, on_delete=db_models.CASCADE)
    slot = db_models.ForeignKey(Slot, on_delete=db_models.CASCADE)

    def __str__(self):
        return f"{self.user.name}-{self.slot.cinema.slug}-{self.slot.movie.slug}"


class BookingSeat(common_models.TimeStampModel):
    """
    Represents an individual seat under a booking.
    - Connects a booking to a specific cinema seat.
    """
    cinema_seat = db_models.ForeignKey(CinemaSeat, on_delete=db_models.CASCADE)
    booking = db_models.ForeignKey(
        Booking, on_delete=db_models.CASCADE, null=True, related_name="seats")

    def __str__(self):
        return f"{self.cinema_seat}"
