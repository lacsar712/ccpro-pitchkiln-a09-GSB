"""灶台相位切换与出胶称重联锁业务规则。"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.utils import timezone

DRAWING_SOFT_POINT_MAX = Decimal("95")


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


def weigh_total_kg(run) -> Decimal:
    """当前值守累计出胶净重(kg)。称重登记与收灶判定共用同一口径。"""
    return run.weighs.aggregate(total=Sum("netKg"))["total"] or Decimal("0.00")


def close_half_kg(run) -> Decimal:
    """收灶半额口径：当前值守来脂批到货千克的一半。"""
    return run.resinLot.arrivalKg / 2


def assert_can_weigh(hearth, net_kg) -> None:
    """
    登记出胶称重前校验：
    - 仅出胶相位灶台可称重，其它相位拒绝；
    - 须有进行中的值守；
    - 未收灶期间累计净重（含本次）不得超过当前值守来脂批到货千克，
      超出拒绝并回显已累计。
    """
    from apps.kiln.models import FireHearth

    if hearth.phase != FireHearth.PHASE_DRAWING:
        raise ValidationError(
            f"仅出胶相位灶台可登记称重（当前相位：{hearth.get_phase_display()}）。"
        )
    run = hearth.open_run()
    if run is None:
        raise ValidationError("该灶没有进行中的值守，无法登记称重。")
    accumulated = weigh_total_kg(run)
    arrival = run.resinLot.arrivalKg
    if accumulated + net_kg > arrival:
        raise ValidationError(
            f"超出来脂批到货量：本值守已累计 {accumulated} kg，"
            f"本次 {net_kg} kg 登记后将达 {accumulated + net_kg} kg，"
            f"超过到货 {arrival} kg。"
        )


def assert_can_close_run(hearth) -> None:
    """
    出胶灶收灶联锁：须至少一条称重，且累计净重不小于到货千克的一半
    （半额口径），否则拒绝。非出胶相位不触发该联锁。
    """
    from apps.kiln.models import FireHearth

    if hearth.phase != FireHearth.PHASE_DRAWING:
        return
    run = hearth.open_run()
    if run is None:
        return
    if not run.weighs.exists():
        raise ValidationError(
            "出胶灶收灶须至少登记一条称重（当前值守尚无称重记录）。"
        )
    total = weigh_total_kg(run)
    half = close_half_kg(run)
    if total < half:
        raise ValidationError(
            f"累计净重 {total} kg 未达半额口径："
            f"到货 {run.resinLot.arrivalKg} kg 的一半 {half} kg，"
            "不得收灶回冷灶。"
        )


def close_run_to_cold(hearth):
    """收灶统一入口：出胶灶先过称重联锁，再收尾值守、灶台回冷灶。"""
    from apps.kiln.models import FireHearth

    run = hearth.open_run()
    if run is None:
        raise ValidationError("没有进行中的值守可收灶")
    assert_can_close_run(hearth)
    run.closedAt = timezone.now()
    run.save(update_fields=["closedAt"])
    hearth.phase = FireHearth.PHASE_COLD
    hearth.save(update_fields=["phase"])
    return run


def change_hearth_phase(hearth, new_phase: str):
    """统一入口：改相位时校验出胶规则并保存。"""
    from apps.kiln.models import FireHearth

    if new_phase == FireHearth.PHASE_DRAWING:
        assert_can_enter_drawing(hearth)
    if (
        new_phase == FireHearth.PHASE_COLD
        and hearth.phase == FireHearth.PHASE_DRAWING
    ):
        raise ValidationError(
            {
                "phase": (
                    "出胶灶回冷灶须走「收灶」入口："
                    "先满足称重联锁（至少一条称重且累计净重达半额）。"
                )
            }
        )

    hearth.phase = new_phase
    hearth.save(update_fields=["phase"])
    return hearth
