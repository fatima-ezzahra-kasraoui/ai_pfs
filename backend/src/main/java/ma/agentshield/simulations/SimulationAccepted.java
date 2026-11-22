package ma.agentshield.simulations;

/** Reponse 202 de POST /api/simulations/run. */
public record SimulationAccepted(String simulationId, SimulationStatus status) {
}
