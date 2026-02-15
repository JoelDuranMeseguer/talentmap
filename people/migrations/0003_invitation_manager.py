# Generated manually

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("people", "0002_add_invitation"),
    ]

    operations = [
        migrations.AddField(
            model_name="invitation",
            name="manager",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="invited_reports",
                to="people.employee",
            ),
        ),
    ]
