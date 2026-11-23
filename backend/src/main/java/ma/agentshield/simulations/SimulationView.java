package ma.agentshield.simulations;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;

/** Reponse de GET /api/simulations/{id} (schema Simulation du contrat). */
public record SimulationView(
        String simulationId,
        String scenarioId,
        SimulationStatus status,
        Instant createdAt,
        Instant completedAt,
        String error,
        SimulationRunView unprotected,
        @JsonProperty("protected") SimulationRunView protectedRun) {
}
