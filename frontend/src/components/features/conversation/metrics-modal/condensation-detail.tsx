import React from "react";
import { useTranslation } from "react-i18next";
import { I18nKey } from "#/i18n/declaration";
import type {
  TokenTimelineEntry,
  CondensationDetail,
} from "#/stores/token-timeline-store";

interface CondensationDetailCardProps {
  detail: CondensationDetail;
  entries: TokenTimelineEntry[];
  onClose: () => void;
}

/**
 * CondensationDetailCard — shows details of a condensation event
 * when the user clicks a condensation marker on the timeline chart.
 */
export function CondensationDetailCard({
  detail,
  entries,
  onClose,
}: CondensationDetailCardProps) {
  const { t } = useTranslation();
  // Find the entry at the condensation turn and the entry just before
  const condensedEntry = entries.find((e) => e.turn === detail.turn);
  const prevEntry = entries.find((e) => e.turn === detail.turn - 1);

  const beforeTokens = prevEntry?.prompt_tokens ?? null;
  const afterTokens = condensedEntry?.prompt_tokens ?? null;

  const tokenDrop =
    beforeTokens !== null && afterTokens !== null
      ? beforeTokens - afterTokens
      : null;
  const tokenDropPct =
    tokenDrop !== null && beforeTokens !== null && beforeTokens > 0
      ? ((tokenDrop / beforeTokens) * 100).toFixed(1)
      : null;

  const condenserTokens = condensedEntry?.condenser_prompt_tokens ?? null;

  return (
    <div className="rounded-md p-3 bg-neutral-800 border border-neutral-600 text-sm">
      <div className="flex items-center justify-between mb-2">
        <span className="font-semibold text-red-400">
          {t(I18nKey.CONVERSATION$CONDENSATION_AT_TURN, {
            turn: detail.turn,
          })}
        </span>
        <button
          type="button"
          onClick={onClose}
          className="text-neutral-400 hover:text-white text-xs"
        >
          {t(I18nKey.CONVERSATION$CLOSE)}
        </button>
      </div>

      <div className="grid gap-1 text-xs">
        {beforeTokens !== null && (
          <div className="flex justify-between">
            <span className="text-neutral-400">
              {t(I18nKey.CONVERSATION$BEFORE)}
            </span>
            <span>
              {beforeTokens.toLocaleString()}{" "}
              {t(I18nKey.CONVERSATION$PROMPT_TOKENS_LABEL)}
            </span>
          </div>
        )}
        {afterTokens !== null && (
          <div className="flex justify-between">
            <span className="text-neutral-400">
              {t(I18nKey.CONVERSATION$AFTER)}
            </span>
            <span>
              {afterTokens.toLocaleString()}{" "}
              {t(I18nKey.CONVERSATION$PROMPT_TOKENS_LABEL)}
            </span>
          </div>
        )}
        {tokenDrop !== null && (
          <div className="flex justify-between">
            <span className="text-neutral-400">
              {t(I18nKey.CONVERSATION$DROP)}
            </span>
            <span className="text-red-400">
              -{tokenDrop.toLocaleString()}{" "}
              {tokenDropPct !== null ? `(-${tokenDropPct}%)` : ""}
            </span>
          </div>
        )}

        <div className="flex justify-between">
          <span className="text-neutral-400">
            {t(I18nKey.CONVERSATION$FORGOTTEN_EVENTS)}
          </span>
          <span>{detail.forgotten_event_ids_count}</span>
        </div>

        {condenserTokens !== null && (
          <div className="flex justify-between">
            <span className="text-neutral-400">
              {t(I18nKey.CONVERSATION$CONDENSER_COST)}
            </span>
            <span>
              {condenserTokens.toLocaleString()}{" "}
              {t(I18nKey.CONVERSATION$PROMPT_TOKENS_LABEL)}
            </span>
          </div>
        )}

        {detail.summary && (
          <div className="mt-1 pt-1 border-t border-neutral-700">
            <span className="text-neutral-400">
              {t(I18nKey.CONVERSATION$SUMMARY_LABEL)}
            </span>
            <p className="mt-0.5 text-neutral-300 line-clamp-3">
              {detail.summary}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
