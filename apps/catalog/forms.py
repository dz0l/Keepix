from django import forms
from django.conf import settings

from .models import CatalogObject


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultiFileField(forms.FileField):
    widget = MultiFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        if not isinstance(data, (list, tuple)):
            data = [data]
        return [super().clean(entry, initial) for entry in data]


class CatalogObjectForm(forms.ModelForm):
    photos = MultiFileField(
        label='Добавить фото',
        required=False,
        widget=MultiFileInput(attrs={'accept': 'image/*,.heic,.heif', 'class': 'input'}),
    )
    pdfs = MultiFileField(
        label='Добавить PDF',
        required=False,
        widget=MultiFileInput(attrs={'accept': 'application/pdf', 'class': 'input'}),
    )

    class Meta:
        model = CatalogObject
        fields = [
            'sender',
            'obj_type',
            'description',
            'comment',
            'placement',
            'condition',
        ]
        widgets = {
            'sender': forms.TextInput(attrs={'autocomplete': 'off'}),
            'description': forms.Textarea(attrs={'rows': 4}),
            'comment': forms.Textarea(attrs={'rows': 3}),
            'placement': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.existing_photo_count = kwargs.pop('existing_photo_count', 0)
        self.existing_pdf_count = kwargs.pop('existing_pdf_count', 0)
        super().__init__(*args, **kwargs)
        self.fields['sender'].required = False
        self.fields['description'].required = True
        for name, field in self.fields.items():
            if name in {'photos', 'pdfs'}:
                continue
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault('class', 'input')
            else:
                field.widget.attrs.setdefault('class', 'input')

    def clean_photos(self):
        files = self.cleaned_data.get('photos') or []
        if not files:
            return files
        if self.existing_photo_count + len(files) > settings.MAX_PHOTOS_PER_ITEM:
            raise forms.ValidationError(f'Не более {settings.MAX_PHOTOS_PER_ITEM} фото на объект.')
        return files

    def clean_pdfs(self):
        files = self.cleaned_data.get('pdfs') or []
        if not files:
            return files
        if self.existing_pdf_count + len(files) > settings.MAX_PDFS_PER_ITEM:
            raise forms.ValidationError(f'Не более {settings.MAX_PDFS_PER_ITEM} PDF на объект.')
        return files
