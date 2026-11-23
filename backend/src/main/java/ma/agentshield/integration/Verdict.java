package ma.agentshield.integration;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.util.Map;

/** Verdict d'un guard (contrat : docs/contract/verdict.schema.json). {@code decision} est nul tant que le moteur n'a pas tranche. */
@JsonIgnoreProperties(ignoreUnknown = true)
public record Verdict(
        String module,
        String attackType,
        double score,
        String riskLevel,
        String decision,
        String reason,
        String correlationId,
        String cleaned,
        Boolean degraded,
        Double latencyMs,
        Map<String, Object> metadata) {
}
