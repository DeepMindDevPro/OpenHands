import React, { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { I18nKey } from "#/i18n/declaration";
import useTokenTimelineStore from "#/stores/token-timeline-store";
import type { CondensationDetail } from "#/stores/token-timeline-store";
import { CondensationDetailCard } from "./condensation-detail";

/** Chart dimensions */
const CHART_WIDTH = 500;
const CHART_HEIGHT = 200;
const PADDING = { top: 20, right: 60, bottom: 30, left: 70 };

/**
 * TokenTimelineChart — SVG-based line chart showing token usage over turns.
 *
 * Shows:
 * - Blue line: prompt_tokens (accumulated)
 * - Green area: usage rate (per_turn_token / context_window)
 * - Red vertical lines: condensation events
 * - Gray dashed line: context_window limit
 */
export function TokenTimelineChart() {
  const { t } = useTranslation();
  const { entries, condensationDetails } = useTokenTimelineStore();
  // eslint-disable-next-line no-console
  console.log(
    "[TOKEN-TIMELINE-CHART] entries:",
    entries.length,
    entries.slice(0, 2),
  );
  const [selectedCondensation, setSelectedCondensation] =
    useState<CondensationDetail | null>(null);

  const plotArea = useMemo(
    () => ({
      width: CHART_WIDTH - PADDING.left - PADDING.right,
      height: CHART_HEIGHT - PADDING.top - PADDING.bottom,
    }),
    [],
  );

  const { maxPrompt, maxTurn } = useMemo(() => {
    if (entries.length === 0) return { maxPrompt: 1, maxTurn: 1 };
    const mp = Math.max(...entries.map((e) => e.prompt_tokens), 1);
    const mt = entries.length;
    return { maxPrompt: mp, maxTurn: mt };
  }, [entries]);

  const contextWindow = useMemo(
    () => entries[entries.length - 1]?.context_window || 0,
    [entries],
  );

  const scaleX = useMemo(
    () => (turn: number) =>
      PADDING.left + ((turn - 1) / Math.max(maxTurn - 1, 1)) * plotArea.width,
    [maxTurn, plotArea.width],
  );

  const scaleY = useMemo(
    () => (tokens: number) =>
      PADDING.top +
      plotArea.height -
      (tokens / Math.max(maxPrompt * 1.1, contextWindow || 1)) *
        plotArea.height,
    [maxPrompt, contextWindow, plotArea],
  );

  // Build prompt_tokens line path
  const promptLinePath = useMemo(() => {
    if (entries.length === 0) return "";
    return entries
      .map(
        (e, i) =>
          `${i === 0 ? "M" : "L"}${scaleX(e.turn).toFixed(1)},${scaleY(e.prompt_tokens).toFixed(1)}`,
      )
      .join(" ");
  }, [entries, scaleX, scaleY]);

  // Build usage rate area path
  const usageAreaPath = useMemo(() => {
    if (entries.length === 0 || !contextWindow) return "";
    const maxRate = 1;
    const scaleRateY = (rate: number) =>
      PADDING.top + plotArea.height - rate * plotArea.height;

    const top = entries
      .map((e, i) => {
        const rate = Math.min(e.per_turn_token / contextWindow, maxRate);
        return `${i === 0 ? "M" : "L"}${scaleX(e.turn).toFixed(1)},${scaleRateY(rate).toFixed(1)}`;
      })
      .join(" ");
    const bottom = `${scaleX(entries[entries.length - 1].turn).toFixed(1)},${scaleRateY(0).toFixed(1)} L${scaleX(entries[0].turn).toFixed(1)},${scaleRateY(0).toFixed(1)} Z`;
    return `${top} ${bottom}`;
  }, [entries, contextWindow, scaleX, plotArea]);

  // Condensation turn numbers
  const condensationTurns = useMemo(
    () => condensationDetails.map((d) => d.turn),
    [condensationDetails],
  );

  if (entries.length === 0) {
    return (
      <div className="text-center text-neutral-400 py-8 text-sm">
        {t(I18nKey.CONVERSATION$NO_TOKEN_DATA)}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between text-sm">
        <span className="font-semibold">
          {t(I18nKey.CONVERSATION$TOKEN_TIMELINE)}
        </span>
        <div className="flex gap-3 text-xs text-neutral-400">
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-0.5 bg-blue-400" />
            {t(I18nKey.CONVERSATION$PROMPT_TOKENS_LABEL)}
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-3 bg-green-500/30" />
            {t(I18nKey.CONVERSATION$USAGE_RATE)}
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-0.5 bg-red-400 border-dashed" />
            {t(I18nKey.CONVERSATION$CONDENSATION_LABEL)}
          </span>
        </div>
      </div>

      <svg
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        className="w-full h-auto"
        style={{ maxHeight: "250px" }}
      >
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
          const y = PADDING.top + plotArea.height * (1 - frac);
          const val = Math.round(
            (maxPrompt * 1.1 || contextWindow || 1) * frac,
          );
          return (
            <g key={frac}>
              <line
                x1={PADDING.left}
                y1={y}
                x2={PADDING.left + plotArea.width}
                y2={y}
                stroke="#374151"
                strokeWidth={0.5}
              />
              <text
                x={PADDING.left - 5}
                y={y + 3}
                textAnchor="end"
                fill="#9ca3af"
                fontSize={8}
              >
                {val.toLocaleString()}
              </text>
            </g>
          );
        })}

        {/* Context window dashed line */}
        {contextWindow > 0 && (
          <line
            x1={PADDING.left}
            y1={scaleY(contextWindow)}
            x2={PADDING.left + plotArea.width}
            y2={scaleY(contextWindow)}
            stroke="#6b7280"
            strokeWidth={1}
            strokeDasharray="4,4"
          />
        )}

        {/* Usage rate area (green) */}
        {usageAreaPath && (
          <path d={usageAreaPath} fill="rgba(34,197,94,0.15)" stroke="none" />
        )}

        {/* Prompt tokens line (blue) */}
        {promptLinePath && (
          <path
            d={promptLinePath}
            fill="none"
            stroke="#60a5fa"
            strokeWidth={1.5}
          />
        )}

        {/* Data points */}
        {entries.map((e) => (
          <circle
            key={e.turn}
            cx={scaleX(e.turn)}
            cy={scaleY(e.prompt_tokens)}
            r={e.is_condensed ? 3 : 1.5}
            fill={e.is_condensed ? "#f87171" : "#60a5fa"}
          />
        ))}

        {/* Condensation event vertical lines */}
        {condensationTurns.map((turn) => (
          <g key={`condensation-${turn}`}>
            <line
              x1={scaleX(turn)}
              y1={PADDING.top}
              x2={scaleX(turn)}
              y2={PADDING.top + plotArea.height}
              stroke="#f87171"
              strokeWidth={1}
              strokeDasharray="3,3"
            />
            {/* Clickable marker */}
            <circle
              cx={scaleX(turn)}
              cy={PADDING.top}
              r={4}
              fill="#f87171"
              className="cursor-pointer"
              onClick={() => {
                const detail = condensationDetails.find((d) => d.turn === turn);
                if (detail) setSelectedCondensation(detail);
              }}
            />
          </g>
        ))}

        {/* X-axis labels */}
        {entries
          .filter(
            (e, i) =>
              entries.length <= 20 ||
              i === 0 ||
              i === entries.length - 1 ||
              i % Math.ceil(entries.length / 10) === 0,
          )
          .map((e) => (
            <text
              key={`x-${e.turn}`}
              x={scaleX(e.turn)}
              y={CHART_HEIGHT - 5}
              textAnchor="middle"
              fill="#9ca3af"
              fontSize={8}
            >
              {e.turn}
            </text>
          ))}

        {/* Axis labels */}
        <text
          x={PADDING.left + plotArea.width / 2}
          y={CHART_HEIGHT - 0}
          textAnchor="middle"
          fill="#9ca3af"
          fontSize={9}
        >
          {t(I18nKey.CONVERSATION$TURN_LABEL)}
        </text>
      </svg>

      {/* Condensation detail card */}
      {selectedCondensation && (
        <CondensationDetailCard
          detail={selectedCondensation}
          entries={entries}
          onClose={() => setSelectedCondensation(null)}
        />
      )}
    </div>
  );
}
