from django import forms

from .models import CatalogObject


class CatalogObjectForm(forms.ModelForm):
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
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault('class', 'input')
            else:
                field.widget.attrs.setdefault('class', 'input')
