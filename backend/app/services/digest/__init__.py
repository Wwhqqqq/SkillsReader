"""每日精选 Skill 推送 —— 四池候选、多维评分、结构化 Top N。"""

__all__ = ["select_daily_picks"]


def __getattr__(name: str):
    if name == "select_daily_picks":
        from app.services.digest.engine import select_daily_picks

        return select_daily_picks
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
