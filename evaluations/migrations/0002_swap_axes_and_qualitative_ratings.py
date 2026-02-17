from django.db import migrations, models


def forwards(apps, schema_editor):
    Assess = apps.get_model("evaluations", "QualitativeIndicatorAssessment")
    # met=True -> rating=4 (Siempre), met=False -> rating=1 (Nunca)
    Assess.objects.filter(met=True).update(rating=4)
    Assess.objects.filter(met=False).update(rating=1)


def backwards(apps, schema_editor):
    Assess = apps.get_model("evaluations", "QualitativeIndicatorAssessment")
    # rating>=3 -> met=True
    Assess.objects.filter(rating__gte=3).update(met=True)
    Assess.objects.filter(rating__lt=3).update(met=False)


class Migration(migrations.Migration):

    dependencies = [
        ("evaluations", "0001_initial"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="QualitativeGoal",
            new_name="QuantitativeGoal",
        ),
        migrations.RenameModel(
            old_name="QuantitativeIndicatorAssessment",
            new_name="QualitativeIndicatorAssessment",
        ),
        migrations.AddField(
            model_name="qualitativeindicatorassessment",
            name="rating",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (1, "Nunca"),
                    (2, "Casi nunca"),
                    (3, "Casi siempre"),
                    (4, "Siempre"),
                ],
                default=1,
            ),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(
            model_name="qualitativeindicatorassessment",
            name="met",
        ),
    ]
