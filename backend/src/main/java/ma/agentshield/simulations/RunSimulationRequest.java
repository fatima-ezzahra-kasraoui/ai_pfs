package ma.agentshield.simulations;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;

public record RunSimulationRequest(
        @NotBlank @Pattern(regexp = "^[a-z0-9-]{1,40}$") String scenarioId) {
}
