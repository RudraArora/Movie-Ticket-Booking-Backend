from django.apps import AppConfig

# user App configuration


class UserConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.user"

    def ready(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()

        if not User.objects.filter(name="admin").exists():
            User.objects.create_superuser(
                name="admin",
                email="admin@test.com",
                password="Admin@123",
                phone_number=1234567890
            )