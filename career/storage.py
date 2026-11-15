from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivatePortfolioStorage(FileSystemStorage):
    """Certificates are served only through a permission-checked portfolio view."""

    def __init__(self, *args, **kwargs):
        kwargs["location"] = settings.BASE_DIR / "private_media"
        kwargs["base_url"] = None
        super().__init__(*args, **kwargs)
