package ma.agentshield.events;

/** Decision du moteur de securite (produite par le service IA, jamais par un guard seul). */
public enum Decision {
    ALLOW,
    SANITIZE,
    CONFIRM,
    BLOCK
}
