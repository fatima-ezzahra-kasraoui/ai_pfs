package ma.agentshield.simulations;

/** Cycle de vie d'une simulation. */
public enum SimulationStatus {
    SUBMITTED,
    RUNNING,
    AWAITING_APPROVAL,
    COMPLETED,
    FAILED
}
