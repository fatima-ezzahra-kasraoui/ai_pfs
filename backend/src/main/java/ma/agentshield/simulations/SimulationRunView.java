package ma.agentshield.simulations;

import java.util.List;

/** Une execution de l'agent (sans ou avec protection) telle qu'exposee par l'API. */
public record SimulationRunView(
        String mode,
        List<StepView> steps,
        String finalDecision,
        Boolean attackSucceeded,
        String finalResponse) {

    /** Etape du pipeline (schema PipelineStep du contrat). */
    public record StepView(String name, String status, String module, String decision, Double score, String reason,
            Double latencyMs) {
    }
}
