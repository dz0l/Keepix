from __future__ import annotations

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction


class ObjectIdSequence(models.Model):
    """Atomic counter for catalogue object codes (0001–9999)."""

    id = models.PositiveSmallIntegerField(primary_key=True)
    next_numeric = models.PositiveSmallIntegerField(default=1)

    class Meta:
        verbose_name = 'Счётчик ID объектов'
        verbose_name_plural = 'Счётчик ID объектов'

    @classmethod
    @transaction.atomic
    def allocate_code(cls) -> str:
        row = cls.objects.select_for_update().filter(pk=1).first()
        if row is None:
            try:
                cls.objects.create(pk=1, next_numeric=1)
            except IntegrityError:
                row = cls.objects.select_for_update().get(pk=1)
            else:
                row = cls.objects.select_for_update().get(pk=1)

        num = row.next_numeric
        if num > 9999:
            raise ValidationError('Достигнут лимит кодов объектов (9999).')
        cls.objects.filter(pk=1).update(next_numeric=num + 1)
        return f'{num:04d}'


class CatalogObject(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Активен'
        DELETED = 'deleted', 'Удалён'

    class Condition(models.TextChoices):
        ACTIVE = 'active', 'Норма'
        LOST = 'lost', 'Утерян'
        BROKEN = 'broken', 'Сломан'
        WRITTEN_OFF = 'written_off', 'Списан'

    class ObjectType(models.TextChoices):
        PAINTING = 'painting', 'Картина'
        SCULPTURE = 'sculpture', 'Скульптура'
        SOUVENIR = 'souvenir', 'Сувенир'
        PORCELAIN = 'porcelain', 'Фарфор'
        CLOCK = 'clock', 'Часы'
        BOOK = 'book', 'Книга'
        PANEL = 'panel', 'Панно'
        DISHES = 'dishes', 'Посуда'
        CARPETS = 'carpets', 'Ковры'
        OTHER = 'other', 'Другое'

    code = models.CharField(primary_key=True, max_length=4, editable=False, verbose_name='ID')
    sender = models.CharField(max_length=255, blank=True, verbose_name='От')
    obj_type = models.CharField(max_length=32, choices=ObjectType.choices, verbose_name='Тип')
    description = models.TextField(blank=True, verbose_name='Описание')
    comment = models.TextField(blank=True, verbose_name='Комментарий')
    placement = models.TextField(blank=True, verbose_name='Размещение')
    condition = models.CharField(
        max_length=24,
        choices=Condition.choices,
        default=Condition.ACTIVE,
        verbose_name='Состояние учёта',
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
        verbose_name='Статус',
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name='objects_created',
        on_delete=models.SET_NULL,
        verbose_name='Кем добавлен',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name='objects_updated',
        on_delete=models.SET_NULL,
        verbose_name='Кем изменён',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата добавления')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата изменения')
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name='objects_deleted',
        on_delete=models.SET_NULL,
        verbose_name='Кем удалён',
    )
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата удаления')

    class Meta:
        verbose_name = 'Объект'
        verbose_name_plural = 'Объекты'
        indexes = [
            models.Index(fields=('obj_type',)),
            models.Index(fields=('status',)),
            models.Index(fields=('condition',)),
            GinIndex(fields=['sender'], name='catalog_obj_sender_trgm', opclasses=['gin_trgm_ops']),
            GinIndex(fields=['description'], name='catalog_obj_descr_trgm', opclasses=['gin_trgm_ops']),
            GinIndex(fields=['comment'], name='catalog_obj_comment_trgm', opclasses=['gin_trgm_ops']),
            GinIndex(fields=['placement'], name='catalog_obj_place_trgm', opclasses=['gin_trgm_ops']),
        ]

    def __str__(self) -> str:
        return self.code


class PlacementHistory(models.Model):
    catalog_object = models.ForeignKey(
        CatalogObject,
        on_delete=models.CASCADE,
        related_name='placement_history',
    )
    placement_text = models.TextField(verbose_name='Размещение (снимок)')
    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    class Meta:
        ordering = ('-changed_at',)
        verbose_name = 'История размещения'
        verbose_name_plural = 'История размещения'


class PhotoAttachment(models.Model):
    catalog_object = models.ForeignKey(
        CatalogObject,
        on_delete=models.CASCADE,
        related_name='photos',
    )
    path_original = models.CharField(max_length=500, verbose_name='Оригинал (относит. путь)')
    path_preview = models.CharField(max_length=500, blank=True, verbose_name='Превью')
    original_name = models.CharField(max_length=255)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    size = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('sort_order', 'pk')
        verbose_name = 'Фото объекта'
        verbose_name_plural = 'Фото объектов'


class PdfAttachment(models.Model):
    catalog_object = models.ForeignKey(
        CatalogObject,
        on_delete=models.CASCADE,
        related_name='pdfs',
    )
    path = models.CharField(max_length=500)
    original_name = models.CharField(max_length=255)
    size = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('pk',)
        verbose_name = 'PDF объекта'
        verbose_name_plural = 'PDF объектов'
