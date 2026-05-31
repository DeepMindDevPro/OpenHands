import { useTranslation } from "react-i18next";
import { I18nKey } from "#/i18n/declaration";
import useTokenTimelineStore from "#/stores/token-timeline-store";

interface ContextWindowSectionProps {
  perTurnToken: number;
  contextWindow: number;
}

export function ContextWindowSection({
  perTurnToken,
  contextWindow,
}: ContextWindowSectionProps) {
  const { t } = useTranslation();
  const { entries } = useTokenTimelineStore();

  const usagePercentage =
    contextWindow > 0 ? (perTurnToken / contextWindow) * 100 : 0;
  const progressWidth = Math.min(100, usagePercentage);
  const isNearLimit = usagePercentage > 80;

  // Estimate turns until next condensation based on event count growth
  const currentTurns = entries.length;
  const condenserMaxSize = 240; // SDK default
  const estimatedEventsUntilCondensation = Math.max(
    0,
    condenserMaxSize - currentTurns,
  );

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="font-semibold">
          {t(I18nKey.CONVERSATION$CONTEXT_WINDOW)}
        </span>
      </div>
      <div className="w-full h-1.5 bg-neutral-700 rounded-full overflow-hidden">
        <div
          className={`h-full transition-all duration-300 ${
            isNearLimit ? "bg-red-500" : "bg-blue-500"
          }`}
          style={{ width: `${progressWidth}%` }}
        />
      </div>
      <div className="flex justify-between">
        <span className="text-xs text-neutral-400">
          {perTurnToken.toLocaleString()} / {contextWindow.toLocaleString()} (
          {usagePercentage.toFixed(2)}% {t(I18nKey.CONVERSATION$USED)})
        </span>
      </div>
      {currentTurns > 0 && (
        <div className="flex justify-end">
          <span
            className={`text-xs ${estimatedEventsUntilCondensation < 30 ? "text-yellow-400" : "text-neutral-500"}`}
          >
            {t(I18nKey.CONVERSATION$TURNS_UNTIL_CONDENSATION, {
              count: estimatedEventsUntilCondensation,
              maxSize: condenserMaxSize,
            })}
          </span>
        </div>
      )}
    </div>
  );
}
