"""File storage in the database, for hosts whose disk does not persist, such as Vercel."""
import mimetypes
from io import BytesIO

from django.core.files.base import File
from django.core.files.storage import Storage
from django.urls import reverse
from django.utils.deconstruct import deconstructible


@deconstructible
class DatabaseStorage(Storage):
    def _model(self):
        from .models import StoredFile
        return StoredFile

    def _open(self, name, mode='rb'):
        record = self._model().objects.filter(name=name).first()
        if record is None:
            raise FileNotFoundError(name)
        return File(BytesIO(bytes(record.content)), name=name)

    def _save(self, name, content):
        content.seek(0)
        self._model().objects.update_or_create(
            name=name,
            defaults={
                'content': content.read(),
                'content_type': mimetypes.guess_type(name)[0] or 'application/octet-stream',
            },
        )
        return name

    def exists(self, name):
        return self._model().objects.filter(name=name).exists()

    def delete(self, name):
        self._model().objects.filter(name=name).delete()

    def size(self, name):
        return len(self._model().objects.get(name=name).content)

    def url(self, name):
        return reverse('stored_file', args=[name])

    def get_modified_time(self, name):
        return self._model().objects.values_list('updated_at', flat=True).get(name=name)
