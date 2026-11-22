package ma.agentshield.simulations;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Contenu de {@code simulations.result_json} : les deux executions d'un meme scenario. */
public record SimulationResult(
        SimulationRunView unprotected,
        @JsonProperty("protected") SimulationRunView protectedRun) {
}
