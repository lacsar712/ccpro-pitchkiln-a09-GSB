# Generated manually for PitchKiln-01 draw-weighing interlock

from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("kiln", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DrawWeighing",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("weighedAt", models.DateTimeField(verbose_name="称重时刻")),
                (
                    "netKg",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=10,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0.01"))
                        ],
                        verbose_name="净重(kg)",
                    ),
                ),
                (
                    "weigherName",
                    models.CharField(max_length=80, verbose_name="司秤人"),
                ),
                (
                    "hearth",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="weighings",
                        to="kiln.firehearth",
                        verbose_name="所属灶台",
                    ),
                ),
            ],
            options={
                "verbose_name": "出胶称重",
                "verbose_name_plural": "出胶称重",
                "ordering": ["-weighedAt", "-id"],
            },
        ),
    ]
