from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.api_call import ApiCall
from app.models.job import Job

logger = get_logger("cost_tracker")


class BudgetExhaustedError(Exception):
    pass


@dataclass
class CostConfig:
    """OpenRouter pricing per 1M tokens. Update periodically."""

    models: dict[str, dict[str, float]] = field(
        default_factory=lambda: {
            "qwen/qwen3-coder:free": {"input": 0.0, "output": 0.0},
            "anthropic/claude-sonnet-4": {"input": 3.0, "output": 15.0},
            "google/gemma-4-31b-it:free": {"input": 0.0, "output": 0.0},
        }
    )

    def calculate(self, model: str, input_tokens: int, output_tokens: int) -> float:
        pricing = self.models.get(model, {"input": 0.0, "output": 0.0})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return round(input_cost + output_cost, 6)


class CostTracker:
    """Tracks actual cost per job and enforces the daily budget."""

    def __init__(self, daily_budget_usd: float = None, alert_threshold: float = None):
        self.daily_budget_usd = daily_budget_usd or settings.daily_budget_usd
        self.alert_threshold = alert_threshold or settings.alert_threshold

    async def track_api_call(
        self,
        db: AsyncSession,
        job_id: UUID | None,
        model: str,
        provider: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: int | None = None,
        success: bool = True,
        error_message: str | None = None,
    ) -> float:
        cost = CostConfig().calculate(model, input_tokens, output_tokens)

        db.add(
            ApiCall(
                job_id=job_id,
                model=model,
                provider=provider,
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
                cost_usd=cost,
                latency_ms=latency_ms,
                success=success,
                error_message=error_message,
            )
        )

        if job_id:
            job = await db.get(Job, job_id)
            if job:
                job.cost_actual_usd = float(job.cost_actual_usd or 0.0) + cost

        await db.commit()

        if provider == "openrouter" and cost > 0:
            await self._check_budget(db)

        return cost

    async def _check_budget(self, db: AsyncSession) -> None:
        total = await db.scalar(select(ApiCall.cost_usd).where(ApiCall.provider == "openrouter"))
        daily_cost = float(total or 0.0)

        if daily_cost >= self.daily_budget_usd * self.alert_threshold:
            logger.warning(
                "budget.threshold_reached",
                daily_cost=daily_cost,
                threshold=self.daily_budget_usd,
            )

        if daily_cost >= self.daily_budget_usd:
            logger.error("budget.exhausted", daily_cost=daily_cost)
            raise BudgetExhaustedError("Daily API budget exhausted")
