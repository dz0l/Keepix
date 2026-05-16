from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='catalogobject',
            name='sender',
            field=models.CharField(blank=True, max_length=255, verbose_name='От'),
        ),
    ]
