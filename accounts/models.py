from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Custom User model to enforce unique email addresses for users, as this will be required for social auth"""
    email = models.EmailField(unique=True)