import django.contrib.postgres.indexes
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0002_sender_optional'),
    ]

    operations = [
        migrations.AddField(
            model_name='catalogobject',
            name='tags',
            field=models.TextField(blank=True, verbose_name='Теги'),
        ),
        migrations.AddIndex(
            model_name='catalogobject',
            index=django.contrib.postgres.indexes.GinIndex(
                fields=['tags'],
                name='catalog_obj_tags_trgm',
                opclasses=['gin_trgm_ops'],
            ),
        ),
    ]
