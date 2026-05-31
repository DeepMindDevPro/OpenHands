import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { BaseModalTitle } from "#/components/shared/modals/confirmation-modals/base-modal";
import { ModalBackdrop } from "#/components/shared/modals/modal-backdrop";
import { ModalBody } from "#/components/shared/modals/modal-body";
import { I18nKey } from "#/i18n/declaration";
import { CostSection } from "./cost-section";
import { UsageSection } from "./usage-section";
import { ContextWindowSection } from "./context-window-section";
import { EmptyState } from "./empty-state";
import { TokenTimelineChart } from "./token-timeline-chart";
import useMetricsStore from "#/stores/metrics-store";
import { useActiveConversation } from "#/hooks/query/use-active-conversation";
import { useSandboxMetrics } from "#/hooks/query/use-sandbox-metrics";

type MetricsTab = "overview" | "timeline";

interface MetricsModalProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MetricsModal({ isOpen, onOpenChange }: MetricsModalProps) {
  const { t } = useTranslation();
  const storeMetrics = useMetricsStore();
  const { data: conversation } = useActiveConversation();
  const [activeTab, setActiveTab] = useState<MetricsTab>("overview");

  const conversationId = conversation?.id;
  const conversationUrl = conversation?.conversation_url;
  const sessionApiKey = conversation?.session_api_key;

  // For V1 conversations, fetch metrics directly from the sandbox
  // Only fetch when the modal is open to avoid unnecessary requests
  const { data: sandboxMetrics } = useSandboxMetrics(
    conversationId,
    conversationUrl,
    sessionApiKey,
    isOpen, // Only enable when modal is open
  );

  // Compute the metrics based on conversation version
  const metrics = useMemo(() => {
    if (sandboxMetrics) {
      return {
        cost: sandboxMetrics.accumulated_cost,
        max_budget_per_task: sandboxMetrics.max_budget_per_task,
        usage: sandboxMetrics.accumulated_token_usage
          ? {
              prompt_tokens:
                sandboxMetrics.accumulated_token_usage.prompt_tokens ?? 0,
              completion_tokens:
                sandboxMetrics.accumulated_token_usage.completion_tokens ?? 0,
              cache_read_tokens:
                sandboxMetrics.accumulated_token_usage.cache_read_tokens ?? 0,
              cache_write_tokens:
                sandboxMetrics.accumulated_token_usage.cache_write_tokens ?? 0,
              context_window:
                sandboxMetrics.accumulated_token_usage.context_window ?? 0,
              per_turn_token:
                sandboxMetrics.accumulated_token_usage.per_turn_token ?? 0,
            }
          : null,
      };
    }

    // For non-V1 conversations, use the store metrics
    return storeMetrics;
  }, [sandboxMetrics, storeMetrics]);

  if (!isOpen) return null;

  const tabClass = (tab: MetricsTab) =>
    `px-3 py-1.5 text-sm rounded-md transition-colors ${
      activeTab === tab
        ? "bg-blue-600 text-white"
        : "text-neutral-400 hover:text-white hover:bg-neutral-700"
    }`;

  return (
    <ModalBackdrop onClose={() => onOpenChange(false)}>
      <ModalBody className="items-start border border-tertiary max-h-[80vh] overflow-y-auto">
        <BaseModalTitle title={t(I18nKey.CONVERSATION$METRICS_INFO)} />

        {/* Tab navigation */}
        <div className="flex gap-1 mb-3 w-full">
          <button
            type="button"
            className={tabClass("overview")}
            onClick={() => setActiveTab("overview")}
          >
            {t(I18nKey.CONVERSATION$OVERVIEW)}
          </button>
          <button
            type="button"
            className={tabClass("timeline")}
            onClick={() => setActiveTab("timeline")}
          >
            {t(I18nKey.CONVERSATION$TOKEN_TIMELINE)}
          </button>
        </div>

        <div className="space-y-4 w-full">
          {activeTab === "overview" && (
            <>
              {(metrics?.cost !== null || metrics?.usage !== null) && (
                <div className="rounded-md p-3">
                  <div className="grid gap-3">
                    <CostSection
                      cost={metrics?.cost ?? null}
                      maxBudgetPerTask={metrics?.max_budget_per_task ?? null}
                    />

                    {metrics?.usage !== null && (
                      <>
                        <UsageSection usage={metrics.usage} />
                        <ContextWindowSection
                          perTurnToken={metrics.usage.per_turn_token}
                          contextWindow={metrics.usage.context_window}
                        />
                      </>
                    )}
                  </div>
                </div>
              )}

              {!metrics?.cost && !metrics?.usage && <EmptyState />}
            </>
          )}

          {activeTab === "timeline" && <TokenTimelineChart />}
        </div>
      </ModalBody>
    </ModalBackdrop>
  );
}
