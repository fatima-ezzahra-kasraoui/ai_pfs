package ma.agentshield.integration;

import com.fasterxml.jackson.annotation.JsonInclude;

/**
 * Corps de POST /internal/agent/run (docs/contract/openapi-internal.yaml). {@code message} est OBLIGATOIRE ;
 * {@code mode} vaut "unprotected" ou "protected" ; {@code confirmationPolicy} : "deny" (defaut cote service), "approve"
 * ou "auto". Les champs nuls ne sont pas envoyes.
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record AgentRunRequest(String scenarioId, String message, ToolFixture toolFixture, String mode, String config,
        Integer seed, String confirmationPolicy) {

    /** Contenu impose a un outil simule (ex. un e-mail piege). */
    public record ToolFixture(String name, String content) {
    }

    public static AgentRunRequest of(String scenarioId, String message, ToolFixture fixture, String mode) {
        return new AgentRunRequest(scenarioId, message, fixture, mode, null, null, "auto");
    }
}
