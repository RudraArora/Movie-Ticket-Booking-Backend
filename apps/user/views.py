from django.contrib.auth import get_user_model
from rest_framework import generics, status, permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt import exceptions
from rest_framework_simplejwt import serializers as rest_framework_serializers
from rest_framework_simplejwt import views as rest_framework_views

from apps.user import constants as user_constants, serializers as user_serializers, filters as user_filters
from apps.cinema import models as cinema_models, serializers as cinema_serializers
from apps.common import pagination as common_pagination

User = get_user_model()


class SignupView(generics.CreateAPIView):
    """
    Class based view for the Signup API
    """

    serializer_class = user_serializers.SignupSerializer


class CustomTokenRefreshView(rest_framework_views.TokenRefreshView):
    """
    Custom token refresh view to generate access token on expiring using the refresh token in the cookies

    @param: request The HTTP request object containing the cookies to generate access token.

    Responses:
    ----------
        - 200 OK: New Access Token generated.
        - 401 Unauthorized: Token is invalid or expired.
    """

    def post(self, request, *args, **kwargs):

        cookie_token = request.COOKIES.get("refresh-token")

        if not cookie_token:
            return Response({"message": user_constants.ErrorMessage.REFRESH_TOKEN_NOT_FOUND}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = rest_framework_serializers.TokenRefreshSerializer(
            data={"refresh": cookie_token})

        try:
            serializer.is_valid(raise_exception=True)
        except exceptions.TokenError as e:
            raise exceptions.InvalidToken(e)

        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class LoginView(rest_framework_views.TokenObtainPairView):
    """

    Handle the user authentication and generate refresh token

    @param: request HTTP request object containing the data to authenticate the user.

    Responses:
    ----------
        - 200 OK: User login successfully.
        - 401 Bad Unauthorized: Invalid credentials.
    """

    def post(self, request, *args, **kwargs):
        email = request.data.get("email").lower()
        password = request.data.get("password")
        serializer = self.get_serializer(
            data={"email": email, "password": password})
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data

        response = Response(
            {"access": str(token.get("access"))}, status=status.HTTP_200_OK)

        response.set_cookie(key="refresh-token", value=str(token.get("refresh")),
                            httponly=True, secure=True, samesite="none", max_age=7*24*60*60, path="/")

        return response


class UserView(generics.RetrieveUpdateAPIView):
    """
    User view for fetching details of a user and updating basic details of a user
    """
    serializer_class = user_serializers.UserSerializer
    permission_classes = [IsAuthenticated]

    # Overridden http methods
    http_method_names = [
        "get",
        "patch",
        # HTTP method requests the metadata of a resource
        "head",
        #  HTTP method requests permitted communication options for a given URL
        "options",
    ]

    def get_object(self):
        # Returns the authenticated user
        return self.request.user
    
class PurchaseHistoryView(generics.ListAPIView):
    """
    View for retrieving the purchase history for a user
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = user_serializers.PurchaseHistorySerializer
    pagination_class = common_pagination.CustomCursorPagination

    def get_queryset(self):
        user = self.request.user
        queryset = (
            cinema_models.Booking.objects.filter(user=user)
            .select_related("slot", "slot__cinema__location")
            .prefetch_related("seats")
        )

        manager = user_filters.PurchaseHistoryFilterManager()

        return manager.apply_filters(self.request, queryset)
