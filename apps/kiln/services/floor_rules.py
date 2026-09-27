"""灶台相位切换与出胶称重联锁业务规则。"""
from decimal import ROUND_UP, Decimal
from typing import Any, NamedTuple

from django.core.exceptions import ValidationError
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

DRAWING_SOFT_POINT_MAX = Decimal("95")

# 半额口径：收灶时累计净重须 ≥ 当前值守来脂批到货量 × 50%（按 0.01kg 向上取整）。
DRAWING_CLOSE_MIN_SHARE = Decimal("0.5")
KG_STEP = Decimal("0.01")


class DrawWeighSummary(NamedTuple):
    """同灶当前未收灶值守期间的称重累计（称重登记与收灶判定共用）。"""

    run: Any
    count: int
    totalKg: Decimal
    arrivalKg: Decimal
    requiredKg: Decimal
    remainingKg: Decimal
    ready: bool


def assert_can_enter_drawing(hearth) -> None:
    """
    进入「出胶」相位前：当前未收灶的 CookRun 须至少有一条
    softPointC <= 95 的 SoftPointProbe。
    """
    open_run = hearth.open_run()
    if open_run is None:
        raise ValidationError(
            {"phase": "无法进入出胶：该灶没有进行中的值守纪录。"}
        )

    ok = open_run.probes.filter(softPointC__lte=DRAWING_SOFT_POINT_MAX).exists()
    if not ok:
        raise ValidationError(
            {
                "phase": (
                    "无法进入出胶：进行中值守尚无软化点探针 "
                    f"≤ {DRAWING_SOFT_POINT_MAX}℃。"
                )
            }
        )


def change_hearth_phase(hearth, new_phase: str):
    """统一入口：改相位时校验出胶规则并保存。"""
    from apps.kiln.models import FireHearth

    if new_phase == FireHearth.PHASE_DRAWING:
        assert_can_enter_drawing(hearth)

    hearth.phase = new_phase
    hearth.save(update_fields=["phase"])
    return hearth


def open_weighings(hearth, open_run):
    """当前未收灶值守期间（称重时刻 ≥ 开灶时刻）的同灶称重查询集。"""
    return hearth.weighings.filter(weighedAt__gte=open_run.openedAt)


def draw_weigh_summary(hearth, open_run=None):
    """
    出胶称重累计口径：同灶、当前未收灶值守（称重时刻 ≥ 开灶时刻）。
    称重登记的到货上限判定与收灶的半额判定共用本口径。
    无进行中值守时返回 None。
    """
    if open_run is None:
        open_run = hearth.open_run()
    if open_run is None:
        return None

    agg = open_weighings(hearth, open_run).aggregate(
        count=Count("id"),
        total=Coalesce(Sum("netKg"), Decimal("0.00")),
    )
    arrival = open_run.resinLot.arrivalKg
    required = (arrival * DRAWING_CLOSE_MIN_SHARE).quantize(
        KG_STEP, rounding=ROUND_UP
    )
    total = agg["total"].quantize(KG_STEP)
    return DrawWeighSummary(
        run=open_run,
        count=agg["count"],
        totalKg=total,
        arrivalKg=arrival,
        requiredKg=required,
        remainingKg=max(arrival - total, Decimal("0.00")),
        ready=agg["count"] > 0 and total >= required,
    )


def register_draw_weighing(hearth, *, weighedAt, netKg, weigherName):
    """
    登记出胶称重：仅出胶相位可称，净重须为正；
    同灶未收灶期间累计净重不得超当前值守来脂批到货量。
    """
    from apps.kiln.models import DrawWeighing, FireHearth

    if hearth.phase != FireHearth.PHASE_DRAWING:
        raise ValidationError("仅出胶相位灶台可登记称重，其它相位拒绝。")
    if netKg is None or netKg <= 0:
        raise ValidationError("净重须为正数。")

    summary = draw_weigh_summary(hearth)
    if summary is None:
        raise ValidationError("该灶没有进行中的值守，无法登记称重。")

    projected = summary.totalKg + netKg
    if projected > summary.arrivalKg:
        raise ValidationError(
            "超出到货量，称重被拒绝："
            f"该值守已累计 {summary.totalKg} kg，"
            f"本次 {netKg} kg 后达 {projected} kg，"
            f"超过到货 {summary.arrivalKg} kg。"
        )

    return DrawWeighing.objects.create(
        hearth=hearth,
        weighedAt=weighedAt,
        netKg=netKg,
        weigherName=weigherName,
    )


def assert_can_close_run(hearth) -> None:
    """
    收灶回冷灶前：当前值守须至少一条出胶称重，
    且累计净重达半额口径（到货量 × 50%，按 0.01kg 向上取整）。
    """
    summary = draw_weigh_summary(hearth)
    if summary is None:
        raise ValidationError("没有进行中的值守可收灶。")
    if summary.count == 0:
        raise ValidationError(
            "无法收灶：该值守尚无出胶称重，收灶前须至少登记一条。"
        )
    if summary.totalKg < summary.requiredKg:
        raise ValidationError(
            f"无法收灶：累计净重 {summary.totalKg} kg 未达半额口径"
            f"（到货 {summary.arrivalKg} kg × 50% = {summary.requiredKg} kg）。"
        )


def close_run_to_cold(hearth):
    """收灶并回冷灶：先过称重联锁再落库，禁止绕过联锁直接收灶。"""
    from apps.kiln.models import FireHearth

    assert_can_close_run(hearth)
    open_run = hearth.open_run()
    open_run.closedAt = timezone.now()
    open_run.save(update_fields=["closedAt"])
    hearth.phase = FireHearth.PHASE_COLD
    hearth.save(update_fields=["phase"])
    return open_run
