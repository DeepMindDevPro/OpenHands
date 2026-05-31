import React from "react";
import { useTranslation } from "react-i18next";
import { I18nKey } from "#/i18n/declaration";

interface CondensationMarkerProps {
  forgottenCount: number;
  summary?: string;
}

/**
 * CondensationMarker — inline marker in the chat event stream
 * indicating that a condensation event occurred.
 */
export function CondensationMarker({
  forgottenCount,
  summary,
}: CondensationMarkerProps) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center gap-2 py-2 px-3 my-1 text-xs text-neutral-400 bg-neutral-800/50 rounded border border-neutral-700/50">
      <span className="text-red-400">{"\u{1F504}"}</span>
      <span>
        {t(I18nKey.CONVERSATION$CONTEXT_CONDENSED)} &middot;{" "}
        {forgottenCount === 1
          ? t(I18nKey.CONVERSATION$HISTORICAL_EVENT_SUMMARIZED, {
              count: forgottenCount,
            })
          : t(I18nKey.CONVERSATION$HISTORICAL_EVENTS_SUMMARIZED, {
              count: forgottenCount,
            })}
      </span>
      {summary && (
        <span className="truncate max-w-60 text-neutral-500" title={summary}>
          &mdash; {summary.slice(0, 100)}
          {summary.length > 100 ? "..." : ""}
        </span>
      )}
    </div>
  );
}
