from .base import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
SECRET_KEY = "django-insecure-test-key"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
