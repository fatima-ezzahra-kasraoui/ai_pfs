package ma.agentshield.integration;

import com.fasterxml.jackson.annotation.JsonInclude;

/** Corps de POST /internal/security/analyze (module A, B ou D). */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record AnalyzeRequest(String module, String text, String channel, String correlationId) {
}
