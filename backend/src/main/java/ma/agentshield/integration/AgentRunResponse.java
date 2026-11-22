package ma.agentshield.integration;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.util.List;

/** Reponse de POST /internal/agent/run. CONTRAT PROVISOIRE (voir {@link AgentRunRequest}). */
@JsonIgnoreProperties(ignoreUnknown = true)
public record AgentRunResponse(
        Boolean attackSucceeded,
        Boolean taskSucceeded,
        String finalDecision,
        Integer confirmations,
        Double totalMs,
        List<AgentEvent> events) {

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record AgentEvent(String stage, String module, String decision, Double score, String reason,
            Double latencyMs) {
    }
}
